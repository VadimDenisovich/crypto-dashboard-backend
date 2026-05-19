from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.trade import Trade


class TradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        bot_id: uuid.UUID | None,
        order_id: uuid.UUID | None,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        fee: Decimal,
        strategy: str,
    ) -> Trade:
        trade = Trade(
            bot_id=bot_id,
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            price=price,
            fee=fee,
            strategy=strategy,
        )
        self._session.add(trade)
        await self._session.flush()
        return trade

    async def list_for_bot(
        self,
        bot_id: uuid.UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[Trade]:
        stmt = select(Trade).where(Trade.bot_id == bot_id).order_by(Trade.created_at.desc()).limit(limit)
        if since is not None:
            stmt = stmt.where(Trade.created_at >= since)
        if until is not None:
            stmt = stmt.where(Trade.created_at <= until)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_for_user_bots(
        self,
        bot_ids: Sequence[uuid.UUID],
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[Trade]:
        if not bot_ids:
            return []
        stmt = (
            select(Trade)
            .where(Trade.bot_id.in_(list(bot_ids)))
            .order_by(Trade.created_at.desc())
            .limit(limit)
        )
        if since is not None:
            stmt = stmt.where(Trade.created_at >= since)
        if until is not None:
            stmt = stmt.where(Trade.created_at <= until)
        result = await self._session.execute(stmt)
        return result.scalars().all()
