from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.backtest_job import BacktestJob, BacktestStatus


class BacktestJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        exchange: str,
        strategy_class: str,
        symbol: str,
        timeframe: str,
        params: dict[str, Any],
        date_from: datetime,
        date_to: datetime,
        initial_balance: dict[str, str],
    ) -> BacktestJob:
        job = BacktestJob(
            user_id=user_id,
            status=BacktestStatus.QUEUED.value,
            exchange=exchange,
            strategy_class=strategy_class,
            symbol=symbol,
            timeframe=timeframe,
            params=params,
            date_from=date_from,
            date_to=date_to,
            initial_balance=initial_balance,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> BacktestJob | None:
        return await self._session.get(BacktestJob, job_id)

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> Sequence[BacktestJob]:
        stmt = (
            select(BacktestJob)
            .where(BacktestJob.user_id == user_id)
            .order_by(BacktestJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self, job: BacktestJob, status: BacktestStatus
    ) -> BacktestJob:
        job.status = status.value
        await self._session.flush()
        return job

    async def mark_completed(
        self, job: BacktestJob, result: dict[str, Any]
    ) -> BacktestJob:
        job.status = BacktestStatus.COMPLETED.value
        job.result = result
        job.completed_at = datetime.now(timezone.utc)
        await self._session.flush()
        return job

    async def mark_failed(
        self, job: BacktestJob, error_message: str
    ) -> BacktestJob:
        job.status = BacktestStatus.FAILED.value
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc)
        await self._session.flush()
        return job

    async def delete(self, job: BacktestJob) -> None:
        await self._session.delete(job)
