from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CurrentUser, DbSession, PublisherDep
from src.api.schemas.bot import BotCreateIn, BotOut, BotParamsIn, BotStopIn
from src.repositories.bot_repo import BotRepository
from src.repositories.command_repo import BotCommandRepository
from src.repositories.credential_repo import ExchangeCredentialRepository
from src.services.bot_service import (
    BotForbidden,
    BotInvalidState,
    BotNotFound,
    BotService,
)

router = APIRouter(prefix="/api/bots", tags=["bots"])


def _service(db: DbSession, publisher: PublisherDep) -> BotService:
    return BotService(
        bots=BotRepository(db),
        credentials=ExchangeCredentialRepository(db),
        commands=BotCommandRepository(db),
        publisher=publisher,
    )


@router.get("", response_model=list[BotOut])
async def list_bots(user: CurrentUser, db: DbSession) -> list[BotOut]:
    bots = await BotRepository(db).list_for_user(user.id)
    return [BotOut.model_validate(b) for b in bots]


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
async def create_bot(
    body: BotCreateIn, user: CurrentUser, db: DbSession, publisher: PublisherDep
) -> BotOut:
    try:
        bot = await _service(db, publisher).create(
            user_id=user.id,
            credential_id=body.credential_id,
            strategy_class=body.strategy_class,
            symbol=body.symbol,
            timeframe=body.timeframe,
            params=body.params,
        )
    except BotForbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return BotOut.model_validate(bot)


@router.get("/{bot_id}", response_model=BotOut)
async def get_bot(bot_id: uuid.UUID, user: CurrentUser, db: DbSession) -> BotOut:
    bot = await BotRepository(db).get(bot_id)
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bot not found")
    if bot.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bot not owned")
    return BotOut.model_validate(bot)


@router.post("/{bot_id}/start", response_model=BotOut)
async def start_bot(
    bot_id: uuid.UUID, user: CurrentUser, db: DbSession, publisher: PublisherDep
) -> BotOut:
    try:
        bot = await _service(db, publisher).start(user_id=user.id, bot_id=bot_id)
    except BotNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except BotForbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except BotInvalidState as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return BotOut.model_validate(bot)


@router.post("/{bot_id}/stop", response_model=BotOut)
async def stop_bot(
    bot_id: uuid.UUID,
    body: BotStopIn,
    user: CurrentUser,
    db: DbSession,
    publisher: PublisherDep,
) -> BotOut:
    try:
        bot = await _service(db, publisher).stop(
            user_id=user.id, bot_id=bot_id, close_positions=body.close_positions
        )
    except BotNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except BotForbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except BotInvalidState as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return BotOut.model_validate(bot)


@router.patch("/{bot_id}/params", response_model=BotOut)
async def update_params(
    bot_id: uuid.UUID,
    body: BotParamsIn,
    user: CurrentUser,
    db: DbSession,
    publisher: PublisherDep,
) -> BotOut:
    try:
        bot = await _service(db, publisher).update_params(
            user_id=user.id, bot_id=bot_id, params=body.params
        )
    except BotNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except BotForbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return BotOut.model_validate(bot)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    repo = BotRepository(db)
    bot = await repo.get(bot_id)
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bot not found")
    if bot.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bot not owned")
    await repo.delete(bot)
