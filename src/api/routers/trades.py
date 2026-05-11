from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser, DbSession
from src.api.schemas.market import OrderOut, TradeOut
from src.repositories.bot_repo import BotRepository
from src.repositories.order_repo import OrderRepository
from src.repositories.trade_repo import TradeRepository

router = APIRouter(prefix="/api", tags=["market"])


async def _assert_owned(db, user_id: uuid.UUID, bot_id: uuid.UUID) -> None:
    bot = await BotRepository(db).get(bot_id)
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bot not found")
    if bot.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bot not owned")


@router.get("/trades", response_model=list[TradeOut])
async def list_trades(
    user: CurrentUser,
    db: DbSession,
    bot_id: uuid.UUID = Query(...),
    since: datetime | None = Query(default=None, alias="from"),
    until: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[TradeOut]:
    await _assert_owned(db, user.id, bot_id)
    items = await TradeRepository(db).list_for_bot(bot_id, since=since, until=until, limit=limit)
    return [TradeOut.model_validate(t) for t in items]


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    user: CurrentUser,
    db: DbSession,
    bot_id: uuid.UUID = Query(...),
    since: datetime | None = Query(default=None, alias="from"),
    until: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[OrderOut]:
    await _assert_owned(db, user.id, bot_id)
    items = await OrderRepository(db).list_for_bot(bot_id, since=since, until=until, limit=limit)
    return [OrderOut.model_validate(o) for o in items]
