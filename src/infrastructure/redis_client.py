from __future__ import annotations

from redis.asyncio import Redis, from_url


def create_redis(url: str) -> Redis:
    return from_url(url, encoding="utf-8", decode_responses=True)
