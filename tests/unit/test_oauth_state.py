from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis

from src.infrastructure.oauth_clients import consume_state, issue_state


@pytest.fixture
async def redis() -> FakeRedis:
    r = FakeRedis()
    yield r
    await r.aclose()


async def test_state_roundtrip(redis) -> None:
    state = await issue_state(redis, provider="google")
    assert isinstance(state, str) and len(state) >= 16
    matched = await consume_state(redis, state=state)
    assert matched == "google"


async def test_state_consumed_only_once(redis) -> None:
    state = await issue_state(redis, provider="github")
    assert await consume_state(redis, state=state) == "github"
    assert await consume_state(redis, state=state) is None


async def test_unknown_state_returns_none(redis) -> None:
    assert await consume_state(redis, state="never-issued") is None
