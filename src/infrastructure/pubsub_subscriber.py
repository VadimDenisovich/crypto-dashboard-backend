from __future__ import annotations

import asyncio
import json
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.domain import events
from src.infrastructure.ws_manager import ConnectionManager
from src.logging_setup import get_logger
from src.services.event_projector import EventProjector

log = get_logger(__name__)


async def _process_message(
    session_factory: async_sessionmaker[AsyncSession],
    ws_manager: ConnectionManager,
    redis: Redis,
    channel: str,
    payload: dict[str, Any],
) -> None:
    async with session_factory() as session:
        try:
            await EventProjector(session, ws_manager).handle(channel, payload)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            log.exception("event.processing_failed", channel=channel, error=str(exc))

    # Засекаем момент последнего heartbeat — для диагностики /api/balances/debug
    if channel == events.ENGINE_STATUS:
        from datetime import datetime, timezone
        await redis.set(
            "engine:last_heartbeat",
            datetime.now(timezone.utc).isoformat(),
            ex=120,
        )


async def run_subscriber(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    ws_manager: ConnectionManager,
    *,
    max_backoff_seconds: int = 30,
) -> None:
    """Подписчик engine.* каналов c exponential backoff на переподключения."""

    backoff = 1.0
    while True:
        try:
            async with redis.pubsub() as pubsub:
                await pubsub.subscribe(*events.ENGINE_CHANNELS)
                log.info("pubsub.subscribed", channels=list(events.ENGINE_CHANNELS))
                backoff = 1.0
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    raw = message["data"]
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    try:
                        payload = json.loads(raw) if isinstance(raw, str) else raw
                    except json.JSONDecodeError as exc:
                        log.warning("pubsub.bad_json", channel=channel, error=str(exc))
                        continue
                    if not isinstance(payload, dict):
                        log.warning("pubsub.bad_payload_type", channel=channel)
                        continue
                    await _process_message(session_factory, ws_manager, redis, channel, payload)
        except asyncio.CancelledError:
            log.info("pubsub.cancelled")
            raise
        except Exception as exc:
            log.exception("pubsub.failure", error=str(exc), retry_in=backoff)
            await asyncio.sleep(backoff)
            backoff = min(max_backoff_seconds, backoff * 2)
