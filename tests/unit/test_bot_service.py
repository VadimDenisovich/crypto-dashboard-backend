"""Reproduce the bot start 500 error."""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from src.infrastructure.command_publisher import CommandPublisher
from src.models.bot import Bot, BotStatus
from src.models.bot_command import CommandKind
from src.repositories.bot_repo import BotRepository
from src.repositories.command_repo import BotCommandRepository
from src.repositories.credential_repo import ExchangeCredentialRepository
from src.services.bot_service import BotService


async def test_bot_start_publishes_command() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    publisher = CommandPublisher(redis)

    user_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    # Build a real Bot ORM object
    bot = Bot(
        id=bot_id,
        user_id=user_id,
        credential_id=cred_id,
        strategy_class="SmaCross",
        symbol="BTC/USDT",
        timeframe="1h",
        params={"fast_period": 5, "slow_period": 20, "order_size": "0.001"},
        status=BotStatus.DRAFT,
    )

    # Mock repositories
    bot_repo = AsyncMock(BotRepository)
    bot_repo.get.return_value = bot
    bot_repo.update_status = AsyncMock(return_value=bot)

    cred_repo = AsyncMock(ExchangeCredentialRepository)

    cmd_repo = AsyncMock(BotCommandRepository)
    cmd_repo.create.return_value = None  # doesn't matter

    service = BotService(bots=bot_repo, credentials=cred_repo, commands=cmd_repo, publisher=publisher)
    result = await service.start(user_id=user_id, bot_id=bot_id)
    assert result is not None


async def test_bot_start_already_running_raises() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    publisher = CommandPublisher(redis)

    user_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    bot = Bot(
        id=bot_id,
        user_id=user_id,
        credential_id=cred_id,
        strategy_class="SmaCross",
        symbol="BTC/USDT",
        timeframe="1h",
        params={"fast_period": 5},
        status=BotStatus.RUNNING,
    )

    bot_repo = AsyncMock(BotRepository)
    bot_repo.get.return_value = bot

    cred_repo = AsyncMock(ExchangeCredentialRepository)
    cmd_repo = AsyncMock(BotCommandRepository)

    service = BotService(bots=bot_repo, credentials=cred_repo, commands=cmd_repo, publisher=publisher)
    from src.services.bot_service import BotInvalidState
    with pytest.raises(BotInvalidState):
        await service.start(user_id=user_id, bot_id=bot_id)
