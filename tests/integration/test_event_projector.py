from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest

from src.domain import events
from src.infrastructure.ws_manager import ConnectionManager
from src.models.order import Order
from src.models.strategy_error import StrategyError
from src.services.event_projector import EventProjector


class TestEventProjector:
    """Интеграционные тесты EventProjector: Redis-события → БД + WS-бродкаст."""

    # ── new_trade ────────────────────────────────────────────────

    async def test_new_trade_creates_order_by_bot_id(
        self, session, test_bot, redis
    ):
        projector = EventProjector(session, ConnectionManager())
        bot_id = str(test_bot.id)
        order_id = f"binance-{uuid.uuid4().hex[:8]}"

        payload = {
            "bot_id": bot_id,
            "order_id": order_id,
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "size": "0.001",
            "price": "42500.50",
            "status": "filled",
            "strategy": "SmaCross",
        }
        await projector.handle(events.NEW_TRADE, payload)
        await session.flush()

        from sqlalchemy import select

        result = await session.execute(
            select(Order).where(
                Order.exchange_order_id == order_id,
                Order.bot_id == test_bot.id,
            )
        )
        order = result.scalar_one_or_none()
        assert order is not None, "Order must be persisted"
        assert order.bot_id == test_bot.id
        assert order.symbol == "BTC/USDT"
        assert order.side == "buy"

    async def test_new_trade_without_bot_id_still_writes(
        self, session, redis
    ):
        projector = EventProjector(session, ConnectionManager())
        order_id = f"binance-{uuid.uuid4().hex[:8]}"

        payload = {
            "order_id": order_id,
            "symbol": "ETH/USDT",
            "side": "sell",
            "type": "limit",
            "size": "0.5",
            "price": "3100.00",
            "status": "open",
            "strategy": "MacdCross",
        }
        await projector.handle(events.NEW_TRADE, payload)
        await session.flush()

        # order_id is unique on (exchange_order_id, bot_id) — when bot_id is None,
        # the upsert inserts a row as long as it doesn't collide.
        from sqlalchemy import select

        result = await session.execute(
            select(Order).where(Order.exchange_order_id == order_id)
        )
        order = result.scalar_one_or_none()
        assert order is not None, "Order must be persisted even without bot_id"
        assert order.bot_id is None

    async def test_new_trade_resolves_correct_bot_among_duplicate_strategies(
        self, session, test_user, test_credential, test_bot, redis
    ):
        """Если у пользователя два бота с одинаковым strategy_class,
        новый метод _resolve_bot_by_id должен найти правильный по bot_id."""
        from src.repositories.bot_repo import BotRepository

        # Создаём второго бота с той же стратегией
        repo = BotRepository(session)
        bot2 = await repo.create(
            user_id=test_user.id,
            credential_id=test_credential.id,
            strategy_class="SmaCross",  # та же стратегия
            symbol="ETH/USDT",
            timeframe="15m",
            params={"fast_period": 5, "slow_period": 20, "order_size": "0.01"},
        )
        await session.flush()

        projector = EventProjector(session, ConnectionManager())
        order_id = f"binance-{uuid.uuid4().hex[:8]}"

        # Событие от bot2
        payload = {
            "bot_id": str(bot2.id),
            "order_id": order_id,
            "symbol": "ETH/USDT",
            "side": "buy",
            "type": "market",
            "size": "0.01",
            "price": "3100.00",
            "status": "filled",
            "strategy": "SmaCross",
        }
        await projector.handle(events.NEW_TRADE, payload)
        await session.flush()

        from sqlalchemy import select

        result = await session.execute(
            select(Order).where(
                Order.exchange_order_id == order_id,
                Order.bot_id == bot2.id,
            )
        )
        order = result.scalar_one_or_none()
        assert order is not None
        assert order.bot_id == bot2.id, "Must resolve bot2, not bot1"

    async def test_new_trade_invalid_bot_id_is_logged(
        self, session, caplog, redis
    ):
        projector = EventProjector(session, ConnectionManager())
        order_id = f"binance-{uuid.uuid4().hex[:8]}"

        payload = {
            "bot_id": "not-a-uuid",
            "order_id": order_id,
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "market",
            "size": "0.001",
            "price": "42000",
            "status": "filled",
            "strategy": "SmaCross",
        }
        await projector.handle(events.NEW_TRADE, payload)
        await session.flush()

        # Order still persisted, bot_id = None
        from sqlalchemy import select

        result = await session.execute(
            select(Order).where(Order.exchange_order_id == order_id)
        )
        order = result.scalar_one_or_none()
        assert order is not None
        assert order.bot_id is None

    # ── strategy_error ───────────────────────────────────────────

    async def test_strategy_error_links_to_bot_by_id(
        self, session, test_bot, redis
    ):
        projector = EventProjector(session, ConnectionManager())

        payload = {
            "bot_id": str(test_bot.id),
            "strategy": "SmaCross",
            "kind": "risk_rejected",
            "message": "insufficient balance",
        }
        await projector.handle(events.STRATEGY_ERROR, payload)
        await session.flush()

        from sqlalchemy import select

        result = await session.execute(
            select(StrategyError).where(StrategyError.bot_id == test_bot.id)
        )
        errors = result.scalars().all()
        assert len(errors) == 1
        assert errors[0].bot_id == test_bot.id
        assert errors[0].strategy == "SmaCross"
        assert errors[0].kind == "risk_rejected"
        assert errors[0].message == "insufficient balance"

    async def test_strategy_error_without_bot_id(
        self, session, redis
    ):
        projector = EventProjector(session, ConnectionManager())

        payload = {
            "strategy": "SmaCross",
            "kind": "execution_failed",
            "message": "exchange unavailable",
        }
        await projector.handle(events.STRATEGY_ERROR, payload)
        await session.flush()

        from sqlalchemy import select

        result = await session.execute(
            select(StrategyError).where(
                StrategyError.strategy == "SmaCross",
                StrategyError.kind == "execution_failed",
            )
        )
        errors = result.scalars().all()
        assert len(errors) == 1
        assert errors[0].bot_id is None

    # ── balance_update ──────────────────────────────────────────

    async def test_balance_update_persists_snapshots(
        self, session, test_credential, redis
    ):
        projector = EventProjector(session, ConnectionManager())

        payload = {
            "credential_id": str(test_credential.id),
            "balances": {
                "USDT": {"free": "10000.00", "used": "500.00", "total": "10500.00"},
                "BTC": {"free": "0.001", "used": "0.0", "total": "0.001"},
            },
        }
        await projector.handle(events.BALANCE_UPDATE, payload)
        await session.flush()

        from sqlalchemy import select
        from src.models.balance_snapshot import BalanceSnapshot

        result = await session.execute(
            select(BalanceSnapshot).where(
                BalanceSnapshot.credential_id == test_credential.id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        currencies = {r.currency for r in rows}
        assert currencies == {"USDT", "BTC"}

    # ── positions_update ────────────────────────────────────────

    async def test_positions_update_persists_snapshots(
        self, session, test_credential, redis
    ):
        projector = EventProjector(session, ConnectionManager())

        payload = {
            "credential_id": str(test_credential.id),
            "positions": [
                {
                    "symbol": "BTC/USDT",
                    "side": "long",
                    "entry_price": "42000.00",
                    "size": "0.001",
                    "current_pnl": "50.00",
                }
            ],
        }
        await projector.handle(events.POSITIONS_UPDATE, payload)
        await session.flush()

        from sqlalchemy import select
        from src.models.position_snapshot import PositionSnapshot

        result = await session.execute(
            select(PositionSnapshot).where(
                PositionSnapshot.credential_id == test_credential.id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].symbol == "BTC/USDT"

    # ── engine_status ───────────────────────────────────────────

    async def test_engine_status_is_logged(self, session, caplog, redis):
        import logging

        from src.logging_setup import get_logger
        from src.services.event_projector import log as projector_log

        projector = EventProjector(session, ConnectionManager())

        with caplog.at_level(logging.INFO, logger=projector_log.name):
            await projector.handle(events.ENGINE_STATUS, {"uptime": 120, "active_bots": ["id1"]})

        assert any(
            "engine.status" in r.message for r in caplog.records
        )

    # ── unknown channel ─────────────────────────────────────────

    async def test_unknown_channel_is_logged(self, session, caplog, redis):
        import logging

        from src.services.event_projector import log as projector_log

        projector = EventProjector(session, ConnectionManager())

        with caplog.at_level(logging.WARNING, logger=projector_log.name):
            await projector.handle("engine.unknown_channel", {"data": 1})

        assert any(
            "event.unknown_channel" in r.message for r in caplog.records
        )
