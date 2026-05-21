from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bot import Bot, BotStatus


class BotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Bot]:
        result = await self._session.execute(select(Bot).where(Bot.user_id == user_id))
        return result.scalars().all()

    async def get(self, bot_id: uuid.UUID) -> Bot | None:
        return await self._session.get(Bot, bot_id)

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        credential_id: uuid.UUID,
        strategy_class: str,
        symbol: str,
        timeframe: str,
        params: dict[str, Any],
    ) -> Bot:
        bot = Bot(
            user_id=user_id,
            credential_id=credential_id,
            strategy_class=strategy_class,
            symbol=symbol,
            timeframe=timeframe,
            params=params,
            status=BotStatus.DRAFT.value,
        )
        self._session.add(bot)
        await self._session.flush()
        return bot

    async def update_status(self, bot: Bot, status: BotStatus) -> Bot:
        bot.status = status.value
        await self._session.flush()
        return bot

    async def update_status_by_id(self, bot_id: uuid.UUID, status: BotStatus) -> None:
        """Прямой UPDATE без загрузки ORM-объекта — для event projector'а."""
        stmt = (
            update(Bot)
            .where(Bot.id == bot_id)
            .values(status=status.value)
        )
        await self._session.execute(stmt)

    async def list_by_statuses(self, statuses: Sequence[BotStatus]) -> Sequence[Bot]:
        result = await self._session.execute(
            select(Bot).where(Bot.status.in_([s.value for s in statuses]))
        )
        return result.scalars().all()

    async def update_params(self, bot: Bot, params: dict[str, Any]) -> Bot:
        bot.params = params
        await self._session.flush()
        return bot

    async def delete(self, bot: Bot) -> None:
        await self._session.delete(bot)
