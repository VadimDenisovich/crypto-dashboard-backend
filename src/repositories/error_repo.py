from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.strategy_error import StrategyError


class StrategyErrorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        bot_id: uuid.UUID | None,
        strategy: str | None,
        kind: str,
        message: str,
        raw: dict[str, Any],
    ) -> None:
        err = StrategyError(
            bot_id=bot_id,
            strategy=strategy,
            kind=kind,
            message=message,
            raw=raw,
        )
        self._session.add(err)
