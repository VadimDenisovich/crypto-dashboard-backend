"""Backtest API router.

Endpoints:
- POST /api/backtest/run        — создать job (queued), кладёт id в очередь
- GET  /api/backtest/{id}       — деталь job'а (для polling'а на фронте)
- GET  /api/backtest            — список своих job'ов
- DELETE /api/backtest/{id}     — удалить (404 если running)
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import CurrentUser, DbSession, get_backtest_queue
from src.api.schemas.backtest import (
    BacktestJobOut,
    BacktestJobSummaryOut,
    BacktestRunIn,
)
from src.repositories.backtest_repo import BacktestJobRepository

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestJobOut, status_code=status.HTTP_201_CREATED)
async def run_backtest(
    body: BacktestRunIn,
    user: CurrentUser,
    db: DbSession,
    queue: asyncio.Queue[uuid.UUID] = Depends(get_backtest_queue),
) -> BacktestJobOut:
    if body.date_to <= body.date_from:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "date_to must be > date_from")
    repo = BacktestJobRepository(db)
    job = await repo.create(
        user_id=user.id,
        strategy_class=body.strategy_class,
        symbol=body.symbol,
        timeframe=body.timeframe,
        params=body.params,
        date_from=body.date_from,
        date_to=body.date_to,
        initial_balance=body.initial_balance,
    )
    await db.commit()
    await queue.put(job.id)
    return BacktestJobOut.model_validate(job)


@router.get("/{job_id}", response_model=BacktestJobOut)
async def get_backtest(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> BacktestJobOut:
    job = await BacktestJobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "backtest job not found")
    if job.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not owned")
    return BacktestJobOut.model_validate(job)


@router.get("", response_model=list[BacktestJobSummaryOut])
async def list_backtests(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[BacktestJobSummaryOut]:
    jobs = await BacktestJobRepository(db).list_for_user(
        user.id, limit=limit, offset=offset
    )
    summaries: list[BacktestJobSummaryOut] = []
    for j in jobs:
        result = j.result or {}
        summaries.append(
            BacktestJobSummaryOut(
                id=j.id,
                status=j.status,
                strategy_class=j.strategy_class,
                symbol=j.symbol,
                timeframe=j.timeframe,
                created_at=j.created_at,
                completed_at=j.completed_at,
                total_return_pct=result.get("total_return_pct"),
                trades_count=result.get("trades_count"),
            )
        )
    return summaries


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest(
    job_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    repo = BacktestJobRepository(db)
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "backtest job not found")
    if job.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not owned")
    if job.status == "running":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "cannot delete a running job; wait until it completes",
        )
    await repo.delete(job)
    await db.commit()
