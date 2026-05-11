from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain import events
from src.infrastructure.command_publisher import CommandPublisher


@pytest.mark.asyncio
async def test_publish_start() -> None:
    redis = AsyncMock()
    pub = CommandPublisher(redis)
    bot_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    cmd_id = uuid.uuid4()

    await pub.start(
        bot_id=bot_id,
        strategy_class="SmaCross",
        symbol="BTC/USDT",
        timeframe="5m",
        params={"x": 1},
        credentials_ref=cred_id,
        command_id=cmd_id,
    )

    redis.publish.assert_awaited_once()
    channel, body = redis.publish.await_args.args
    assert channel == events.COMMAND_START
    decoded = json.loads(body)
    assert decoded["bot_id"] == str(bot_id)
    assert decoded["credentials_ref"] == str(cred_id)
    assert decoded["command_id"] == str(cmd_id)


@pytest.mark.asyncio
async def test_publish_stop_and_update() -> None:
    redis = AsyncMock()
    pub = CommandPublisher(redis)
    bot_id = uuid.uuid4()

    await pub.stop(bot_id=bot_id, close_positions=True, command_id=uuid.uuid4())
    await pub.update(bot_id=bot_id, params={"a": 2}, command_id=uuid.uuid4())

    assert redis.publish.await_count == 2
    channels = [call.args[0] for call in redis.publish.await_args_list]
    assert channels == [events.COMMAND_STOP, events.COMMAND_UPDATE]
