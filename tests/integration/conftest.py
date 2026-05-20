from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ══ Переопределяем переменные окружения ДО импорта src.*,
# чтобы test-рантайм get_settings() прочитал правильные секреты.
# tests/conftest.py (родительский) делает setdefault, поэтому здесь
# прямо перезаписываем.
TEST_JWT_SECRET = "integration-test-jwt-secret-at-least-32-chars"
TEST_ENCRYPTION_KEY = "ZmRldi1mZXJuZXQta2V5LXBsZWFzZS1jaGFuZ2UtaW4tcHJvZD0="

os.environ["BACKEND_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["BACKEND_ENCRYPTION_KEY"] = TEST_ENCRYPTION_KEY
os.environ["BACKEND_CAPTCHA_DISABLED"] = "true"

# Теперь можно импортировать src — get_settings() закэширует
# значения из os.environ.
from src.config import Settings, get_settings
from src.infrastructure.crypto import Cipher
from src.infrastructure.security import encode_access_token
from src.infrastructure.ws_manager import ConnectionManager
from src.main import create_app
from src.models.base import Base
from src.models.bot import Bot, BotStatus
from src.models.exchange_credential import ExchangeCredential
from src.models.user import User
from src.repositories.bot_repo import BotRepository
from src.repositories.user_repo import UserRepository

INTEGRATION_DB_URL = os.environ.get(
    "INTEGRATION_DB_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test_db",
)
INTEGRATION_REDIS_URL = os.environ.get(
    "INTEGRATION_REDIS_URL",
    "redis://localhost:6379/1",
)


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(INTEGRATION_DB_URL, pool_pre_ping=True, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture()
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        async with sess.begin():
            yield sess
            await sess.rollback()


@pytest_asyncio.fixture()
async def redis() -> AsyncIterator[Redis]:
    try:
        client = Redis.from_url(
            INTEGRATION_REDIS_URL, encoding="utf-8", decode_responses=True
        )
        await client.ping()
    except Exception:
        pytest.skip("Redis is not available")
    try:
        await client.flushdb()
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture()
async def app(engine: AsyncEngine, session: AsyncSession, redis: Redis) -> AsyncIterator[Any]:
    from src.infrastructure.db import create_session_factory

    factory = create_session_factory(engine)
    cipher = Cipher(TEST_ENCRYPTION_KEY)
    ws_manager = ConnectionManager(max_queue=100, send_timeout=2.0)

    fastapi_app = create_app()
    fastapi_app.state.db_engine = engine
    fastapi_app.state.session_factory = factory
    fastapi_app.state.redis = redis
    fastapi_app.state.cipher = cipher
    fastapi_app.state.ws_manager = ws_manager
    fastapi_app.state.backtest_queue = asyncio.Queue()
    fastapi_app.state.resend = None
    fastapi_app.state.email_codes = None

    yield fastapi_app
    await ws_manager.close_all()


@pytest_asyncio.fixture()
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture()
async def test_user(session: AsyncSession) -> User:
    repo = UserRepository(session)
    user = await repo.create(email="integration-test@example.com")
    await session.flush()
    return user


@pytest_asyncio.fixture()
def access_token(test_user: User) -> str:
    return encode_access_token(
        user_id=test_user.id,
        role=test_user.role.value,
        secret=TEST_JWT_SECRET,
        algorithm="HS256",
        ttl_minutes=15,
    )


@pytest_asyncio.fixture()
async def test_credential(session: AsyncSession, test_user: User) -> ExchangeCredential:
    cipher = Cipher(TEST_ENCRYPTION_KEY)
    cred = ExchangeCredential(
        user_id=test_user.id,
        exchange="binance",
        label="test-key",
        api_key_enc=cipher.encrypt("test-api-key"),
        api_secret_enc=cipher.encrypt("test-api-secret"),
        passphrase_enc=None,
    )
    session.add(cred)
    await session.flush()
    return cred


@pytest_asyncio.fixture()
async def test_bot(
    session: AsyncSession,
    test_user: User,
    test_credential: ExchangeCredential,
) -> Bot:
    repo = BotRepository(session)
    bot = await repo.create(
        user_id=test_user.id,
        credential_id=test_credential.id,
        strategy_class="SmaCross",
        symbol="BTC/USDT",
        timeframe="5m",
        params={"fast_period": 10, "slow_period": 30, "order_size": "0.001"},
    )
    bot.status = BotStatus.RUNNING
    await session.flush()
    return bot
