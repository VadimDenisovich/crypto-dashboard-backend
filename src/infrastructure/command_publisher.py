from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis

from src.domain import events


class CommandPublisher:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def _publish(self, channel: str, payload: dict[str, Any]) -> None:
        await self._redis.publish(channel, json.dumps(payload, default=str))

    async def start(
        self,
        *,
        bot_id: uuid.UUID,
        strategy_class: str,
        symbol: str,
        timeframe: str,
        params: dict[str, Any],
        credentials_ref: uuid.UUID,
        command_id: uuid.UUID,
    ) -> None:
        await self._publish(
            events.COMMAND_START,
            {
                "command_id": str(command_id),
                "bot_id": str(bot_id),
                "strategy_class": strategy_class,
                "symbol": symbol,
                "timeframe": timeframe,
                "params": params,
                "credentials_ref": str(credentials_ref),
            },
        )

    async def stop(
        self,
        *,
        bot_id: uuid.UUID,
        close_positions: bool,
        command_id: uuid.UUID,
    ) -> None:
        await self._publish(
            events.COMMAND_STOP,
            {
                "command_id": str(command_id),
                "bot_id": str(bot_id),
                "close_positions": close_positions,
            },
        )

    async def update(
        self,
        *,
        bot_id: uuid.UUID,
        params: dict[str, Any],
        command_id: uuid.UUID,
    ) -> None:
        await self._publish(
            events.COMMAND_UPDATE,
            {
                "command_id": str(command_id),
                "bot_id": str(bot_id),
                "params": params,
            },
        )
