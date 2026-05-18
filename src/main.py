from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    auth,
    balances,
    bots,
    credentials,
    exchanges,
    health,
    oauth,
    trades,
    ws,
)
from src.config import get_settings
from src.infrastructure.command_publisher import CommandPublisher
from src.infrastructure.crypto import Cipher
from src.infrastructure.db import create_engine, create_session_factory
from src.infrastructure.email_codes import EmailCodeStore
from src.infrastructure.pubsub_subscriber import run_subscriber
from src.infrastructure.redis_client import create_redis
from src.infrastructure.resend_email import ResendClient
from src.infrastructure.ws_manager import ConnectionManager
from src.logging_setup import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.backend_log_level)
    log = get_logger("lifespan")

    engine = create_engine(settings.backend_database_url)
    session_factory = create_session_factory(engine)
    redis = create_redis(settings.backend_redis_url)
    cipher = Cipher(settings.backend_encryption_key)
    publisher = CommandPublisher(redis)
    ws_manager = ConnectionManager(
        max_queue=settings.backend_ws_max_queue,
        send_timeout=settings.backend_ws_send_timeout_seconds,
    )

    resend = ResendClient(
        api_key=settings.resend_api_key,
        sender_email=settings.resend_sender_email,
        sender_name=settings.resend_sender_name,
    )
    email_codes = EmailCodeStore(
        redis,
        ttl_sec=settings.backend_email_code_ttl_sec,
        max_attempts=settings.backend_email_code_max_attempts,
        rate_limit_per_min=settings.backend_email_request_rate_limit_per_min,
    )

    app.state.db_engine = engine
    app.state.session_factory = session_factory
    app.state.redis = redis
    app.state.cipher = cipher
    app.state.publisher = publisher
    app.state.ws_manager = ws_manager
    app.state.resend = resend
    app.state.email_codes = email_codes

    subscriber_task = asyncio.create_task(
        run_subscriber(
            redis,
            session_factory,
            ws_manager,
            max_backoff_seconds=settings.backend_pubsub_reconnect_max_seconds,
        ),
        name="pubsub-subscriber",
    )

    log.info("backend.started")

    try:
        yield
    finally:
        subscriber_task.cancel()
        await asyncio.gather(subscriber_task, return_exceptions=True)
        await ws_manager.close_all()
        await redis.aclose()
        await engine.dispose()
        log.info("backend.stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="crypto-dashboard backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(oauth.router)
    app.include_router(credentials.router)
    app.include_router(bots.router)
    app.include_router(trades.router)
    app.include_router(balances.router)
    app.include_router(exchanges.router)
    app.include_router(ws.router)
    return app


app = create_app()
