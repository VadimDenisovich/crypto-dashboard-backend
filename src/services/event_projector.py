from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain import events
from src.infrastructure.ws_manager import ConnectionManager
from src.logging_setup import get_logger
from src.models.bot import Bot
from src.models.exchange_credential import ExchangeCredential
from src.repositories.balance_repo import BalanceRepository
from src.repositories.error_repo import StrategyErrorRepository
from src.repositories.order_repo import OrderRepository
from src.repositories.position_repo import PositionRepository

log = get_logger(__name__)


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        raise ValueError("decimal value is None")
    return Decimal(str(value))


class EventProjector:
    """Записывает события движка в БД и пересылает их WS-клиентам пользователя."""

    def __init__(self, session: AsyncSession, ws_manager: ConnectionManager) -> None:
        self._session = session
        self._ws = ws_manager

    async def handle(self, channel: str, payload: dict[str, Any]) -> None:
        if channel == events.NEW_TRADE:
            await self._handle_new_trade(payload)
        elif channel == events.BALANCE_UPDATE:
            await self._handle_balance_update(payload)
        elif channel == events.POSITIONS_UPDATE:
            await self._handle_positions_update(payload)
        elif channel == events.STRATEGY_ERROR:
            await self._handle_strategy_error(payload)
        elif channel == events.ENGINE_STATUS:
            await self._broadcast_status(payload)
        else:
            log.warning("event.unknown_channel", channel=channel)

    async def _resolve_bot_for_strategy(self, strategy: str | None) -> Bot | None:
        if not strategy:
            return None
        result = await self._session.execute(
            select(Bot).where(Bot.strategy_class == strategy).limit(1)
        )
        return result.scalar_one_or_none()

    async def _handle_new_trade(self, payload: dict[str, Any]) -> None:
        strategy = payload.get("strategy")
        bot = await self._resolve_bot_for_strategy(strategy)
        bot_id = bot.id if bot else None
        await OrderRepository(self._session).upsert(
            bot_id=bot_id,
            exchange_order_id=str(payload["order_id"]),
            symbol=str(payload["symbol"]),
            side=str(payload["side"]),
            type=str(payload["type"]),
            size=_to_decimal(payload["size"]),
            price=_to_decimal(payload["price"]) if payload.get("price") is not None else None,
            status=str(payload["status"]),
            strategy=str(strategy or ""),
        )
        if bot is not None:
            await self._ws.broadcast_to_user(
                bot.user_id, {"type": "new_trade", "data": payload}
            )

    async def _handle_balance_update(self, payload: dict[str, Any]) -> None:
        credential_id = payload.get("credential_id")
        balances = payload.get("balances", {})
        if credential_id is None:
            log.warning("balance_update.no_credential", payload_keys=list(payload.keys()))
            return
        cred_uuid = uuid.UUID(str(credential_id))
        repo = BalanceRepository(self._session)
        for currency, amounts in balances.items():
            await repo.insert(
                credential_id=cred_uuid,
                currency=str(currency),
                free=_to_decimal(amounts["free"]),
                used=_to_decimal(amounts["used"]),
                total=_to_decimal(amounts["total"]),
            )
        cred = await self._session.get(ExchangeCredential, cred_uuid)
        if cred is not None:
            await self._ws.broadcast_to_user(
                cred.user_id, {"type": "balance_update", "data": payload}
            )

    async def _handle_positions_update(self, payload: dict[str, Any]) -> None:
        credential_id = payload.get("credential_id")
        positions_raw = payload.get("positions", [])
        if credential_id is None:
            log.warning("positions_update.no_credential", payload_keys=list(payload.keys()))
            return
        cred_uuid = uuid.UUID(str(credential_id))
        repo = PositionRepository(self._session)
        for pos in positions_raw:
            await repo.insert(
                credential_id=cred_uuid,
                symbol=str(pos["symbol"]),
                side=str(pos["side"]),
                entry_price=_to_decimal(pos["entry_price"]),
                size=_to_decimal(pos["size"]),
                current_pnl=_to_decimal(pos["current_pnl"]),
            )
        cred = await self._session.get(ExchangeCredential, cred_uuid)
        if cred is not None:
            await self._ws.broadcast_to_user(
                cred.user_id, {"type": "positions_update", "data": payload}
            )

    async def _handle_strategy_error(self, payload: dict[str, Any]) -> None:
        strategy = payload.get("strategy")
        bot = await self._resolve_bot_for_strategy(strategy)
        await StrategyErrorRepository(self._session).insert(
            bot_id=bot.id if bot else None,
            strategy=strategy,
            kind=str(payload.get("kind", "unknown")),
            message=str(payload.get("message", "")),
            raw=payload,
        )
        if bot is not None:
            await self._ws.broadcast_to_user(
                bot.user_id, {"type": "strategy_error", "data": payload}
            )

    async def _broadcast_status(self, payload: dict[str, Any]) -> None:
        log.info("engine.status", **{k: v for k, v in payload.items() if k != "secret"})
