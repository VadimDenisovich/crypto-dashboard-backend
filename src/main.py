from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    auth,
    backtest,
    balances,
    bots,
    candles,
    credentials,
    exchanges,
    health,
    metrics,
    oauth,
    positions,
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
from src.api.routers.metrics import prometheus_middleware
from src.logging_setup import configure_logging, get_logger
from src.services.backtest_worker import backtest_worker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.backend_log_level)
    log = get_logger("lifespan")

    # Для бэктест-subprocess'а: добавляем engine/src в PYTHONPATH
    _add_engine_to_path()

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

    backtest_queue: asyncio.Queue[Any] = asyncio.Queue()

    app.state.db_engine = engine
    app.state.session_factory = session_factory
    app.state.redis = redis
    app.state.cipher = cipher
    app.state.publisher = publisher
    app.state.ws_manager = ws_manager
    app.state.resend = resend
    app.state.email_codes = email_codes
    app.state.backtest_queue = backtest_queue

    subscriber_task = asyncio.create_task(
        run_subscriber(
            redis,
            session_factory,
            ws_manager,
            max_backoff_seconds=settings.backend_pubsub_reconnect_max_seconds,
        ),
        name="pubsub-subscriber",
    )
    backtest_task = asyncio.create_task(
        backtest_worker(backtest_queue, session_factory, settings),
        name="backtest-worker",
    )

    log.info("backend.started")

    try:
        yield
    finally:
        subscriber_task.cancel()
        backtest_task.cancel()
        await asyncio.gather(subscriber_task, backtest_task, return_exceptions=True)
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
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ] if settings.backend_dev_mode else settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(prometheus_middleware)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(oauth.router)
    app.include_router(credentials.router)
    app.include_router(bots.router)
    app.include_router(trades.router)
    app.include_router(balances.router)
    app.include_router(exchanges.router)
    app.include_router(backtest.router)
    app.include_router(ws.router)
    app.include_router(positions.router)
    app.include_router(candles.router)
    return app


app = create_app()


def _add_engine_to_path() -> None:
    """Add trade-engine src to PYTHONPATH so backtest subprocess can find it."""
    import os as _os
    import sys as _sys
    from pathlib import Path as _Path
    candidates = [
        _Path("/opt/engine/src"),  # Docker
    ]
    try:
        # Monorepo local dev: backend/src/main.py → 3 parents → root
        monorepo = _Path(__file__).resolve().parent.parent.parent.parent / "trade-engine-crypto" / "src"
        if monorepo.is_dir():
            candidates.append(monorepo)
    except (IndexError, ValueError):
        pass
    for p in candidates:
        if p.is_dir() and str(p) not in _sys.path:
            _sys.path.insert(0, str(p))
            _os.environ["PYTHONPATH"] = str(p) + ":" + _os.environ.get("PYTHONPATH", "")
