from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.balance_snapshot import BalanceSnapshot


class BalanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        credential_id: uuid.UUID,
        currency: str,
        free: Decimal,
        used: Decimal,
        total: Decimal,
    ) -> None:
        snap = BalanceSnapshot(
            credential_id=credential_id,
            currency=currency,
            free=free,
            used=used,
            total=total,
        )
        self._session.add(snap)

    async def latest_for_credential(self, credential_id: uuid.UUID) -> Sequence[BalanceSnapshot]:
        ranked = (
            select(
                BalanceSnapshot.id.label("id"),
                func.row_number()
                .over(
                    partition_by=BalanceSnapshot.currency,
                    order_by=(
                        BalanceSnapshot.observed_at.desc(),
                        BalanceSnapshot.id.desc(),
                    ),
                )
                .label("rn"),
            )
            .where(BalanceSnapshot.credential_id == credential_id)
            .subquery()
        )
        stmt = (
            select(BalanceSnapshot)
            .join(ranked, BalanceSnapshot.id == ranked.c.id)
            .where(ranked.c.rn == 1)
            .order_by(BalanceSnapshot.currency.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
