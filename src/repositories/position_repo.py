from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.position_snapshot import PositionSnapshot


class PositionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        credential_id: uuid.UUID,
        symbol: str,
        side: str,
        entry_price: Decimal,
        size: Decimal,
        current_pnl: Decimal,
    ) -> None:
        snap = PositionSnapshot(
            credential_id=credential_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            current_pnl=current_pnl,
        )
        self._session.add(snap)

    async def latest_for_credential(self, credential_id: uuid.UUID) -> Sequence[PositionSnapshot]:
        stmt = (
            select(PositionSnapshot)
            .where(PositionSnapshot.credential_id == credential_id)
            .order_by(PositionSnapshot.observed_at.desc())
            .limit(100)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
