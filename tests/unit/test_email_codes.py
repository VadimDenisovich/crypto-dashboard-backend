from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis

from src.infrastructure.email_codes import (
    CodeLocked,
    CodeMismatch,
    CodeNotFound,
    EmailCodeStore,
    RateLimited,
    generate_code,
)


@pytest.fixture
async def redis() -> FakeRedis:
    r = FakeRedis()
    yield r
    await r.aclose()


def test_generate_code_format() -> None:
    for _ in range(50):
        c = generate_code()
        assert len(c) == 6 and c.isdigit()


async def test_issue_then_verify_success(redis) -> None:
    store = EmailCodeStore(redis, ttl_sec=60, max_attempts=5)
    code = await store.issue("user@example.com")
    await store.verify("user@example.com", code)  # not raises


async def test_verify_wrong_code_then_locked_after_max_attempts(redis) -> None:
    store = EmailCodeStore(redis, ttl_sec=60, max_attempts=3)
    await store.issue("u@x.com")
    for _ in range(2):
        with pytest.raises(CodeMismatch):
            await store.verify("u@x.com", "000000")
    with pytest.raises(CodeLocked):
        await store.verify("u@x.com", "000000")
    # После лока ключа уже нет.
    with pytest.raises(CodeNotFound):
        await store.verify("u@x.com", "000000")


async def test_verify_uses_lower_email(redis) -> None:
    store = EmailCodeStore(redis)
    code = await store.issue("Mixed@Example.com")
    await store.verify("mixed@example.com", code)


async def test_no_code_in_redis_raises_not_found(redis) -> None:
    store = EmailCodeStore(redis)
    with pytest.raises(CodeNotFound):
        await store.verify("nobody@example.com", "123456")


async def test_rate_limit_per_ip(redis) -> None:
    store = EmailCodeStore(redis, rate_limit_per_min=2)
    await store.check_rate_limit("1.2.3.4")
    await store.check_rate_limit("1.2.3.4")
    with pytest.raises(RateLimited):
        await store.check_rate_limit("1.2.3.4")
    # другой IP не задет
    await store.check_rate_limit("5.6.7.8")


async def test_rate_limit_skipped_for_empty_ip(redis) -> None:
    store = EmailCodeStore(redis, rate_limit_per_min=1)
    for _ in range(5):
        await store.check_rate_limit("")  # no-op
