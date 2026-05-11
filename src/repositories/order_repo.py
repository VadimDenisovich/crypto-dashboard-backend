from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        bot_id: uuid.UUID | None,
        exchange_order_id: str,
        symbol: str,
        side: str,
        type: str,
        size: Decimal,
        price: Decimal | None,
        status: str,
        strategy: str,
    ) -> None:
        stmt = pg_insert(Order).values(
            bot_id=bot_id,
            exchange_order_id=exchange_order_id,
            symbol=symbol,
            side=side,
            type=type,
            size=size,
            price=price,
            status=status,
            strategy=strategy,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_order_exchange_bot",
            set_={"status": stmt.excluded.status, "size": stmt.excluded.size, "price": stmt.excluded.price},
        )
        await self._session.execute(stmt)

    async def list_for_bot(
        self,
        bot_id: uuid.UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[Order]:
        stmt = select(Order).where(Order.bot_id == bot_id).order_by(Order.created_at.desc()).limit(limit)
        if since is not None:
            stmt = stmt.where(Order.created_at >= since)
        if until is not None:
            stmt = stmt.where(Order.created_at <= until)
        result = await self._session.execute(stmt)
        return result.scalars().all()
