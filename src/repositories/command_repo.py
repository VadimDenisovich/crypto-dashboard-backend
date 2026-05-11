from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bot_command import BotCommand, CommandKind


class BotCommandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        command_id: uuid.UUID,
        bot_id: uuid.UUID,
        kind: CommandKind,
        payload: dict[str, Any],
    ) -> BotCommand:
        record = BotCommand(
            command_id=command_id,
            bot_id=bot_id,
            kind=kind,
            payload=payload,
        )
        self._session.add(record)
        await self._session.flush()
        return record
