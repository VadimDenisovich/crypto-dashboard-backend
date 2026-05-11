from __future__ import annotations

import uuid
from typing import Any

from src.infrastructure.command_publisher import CommandPublisher
from src.models.bot import Bot, BotStatus
from src.models.bot_command import CommandKind
from src.repositories.bot_repo import BotRepository
from src.repositories.command_repo import BotCommandRepository
from src.repositories.credential_repo import ExchangeCredentialRepository


class BotServiceError(Exception):
    pass


class BotNotFound(BotServiceError):
    pass


class BotForbidden(BotServiceError):
    pass


class BotInvalidState(BotServiceError):
    pass


class BotService:
    def __init__(
        self,
        bots: BotRepository,
        credentials: ExchangeCredentialRepository,
        commands: BotCommandRepository,
        publisher: CommandPublisher,
    ) -> None:
        self._bots = bots
        self._credentials = credentials
        self._commands = commands
        self._publisher = publisher

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
        cred = await self._credentials.get(credential_id)
        if cred is None or cred.user_id != user_id:
            raise BotForbidden("credential not found or not owned")
        return await self._bots.create(
            user_id=user_id,
            credential_id=credential_id,
            strategy_class=strategy_class,
            symbol=symbol,
            timeframe=timeframe,
            params=params,
        )

    async def _owned(self, user_id: uuid.UUID, bot_id: uuid.UUID) -> Bot:
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise BotNotFound("bot not found")
        if bot.user_id != user_id:
            raise BotForbidden("bot not owned")
        return bot

    async def start(self, *, user_id: uuid.UUID, bot_id: uuid.UUID) -> Bot:
        bot = await self._owned(user_id, bot_id)
        if bot.status in (BotStatus.RUNNING, BotStatus.STARTING):
            raise BotInvalidState(f"bot is already {bot.status.value}")
        command_id = uuid.uuid4()
        payload: dict[str, Any] = {
            "strategy_class": bot.strategy_class,
            "symbol": bot.symbol,
            "timeframe": bot.timeframe,
            "params": bot.params,
            "credentials_ref": str(bot.credential_id),
        }
        await self._commands.create(
            command_id=command_id, bot_id=bot.id, kind=CommandKind.START, payload=payload
        )
        await self._publisher.start(
            bot_id=bot.id,
            strategy_class=bot.strategy_class,
            symbol=bot.symbol,
            timeframe=bot.timeframe,
            params=bot.params,
            credentials_ref=bot.credential_id,
            command_id=command_id,
        )
        return await self._bots.update_status(bot, BotStatus.STARTING)

    async def stop(self, *, user_id: uuid.UUID, bot_id: uuid.UUID, close_positions: bool) -> Bot:
        bot = await self._owned(user_id, bot_id)
        if bot.status in (BotStatus.STOPPED, BotStatus.DRAFT):
            raise BotInvalidState(f"bot is already {bot.status.value}")
        command_id = uuid.uuid4()
        await self._commands.create(
            command_id=command_id,
            bot_id=bot.id,
            kind=CommandKind.STOP,
            payload={"close_positions": close_positions},
        )
        await self._publisher.stop(
            bot_id=bot.id, close_positions=close_positions, command_id=command_id
        )
        return await self._bots.update_status(bot, BotStatus.STOPPING)

    async def update_params(
        self, *, user_id: uuid.UUID, bot_id: uuid.UUID, params: dict[str, Any]
    ) -> Bot:
        bot = await self._owned(user_id, bot_id)
        command_id = uuid.uuid4()
        await self._commands.create(
            command_id=command_id, bot_id=bot.id, kind=CommandKind.UPDATE, payload={"params": params}
        )
        await self._publisher.update(bot_id=bot.id, params=params, command_id=command_id)
        return await self._bots.update_params(bot, params)
