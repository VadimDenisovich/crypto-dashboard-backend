"""Хранилище одноразовых кодов входа в Redis.

Логика:
- ключ `auth:email_code:{email_lower}` хранит JSON `{hash, attempts, requested_at}` с TTL.
- хэш — bcrypt от plaintext-кода (чтобы Redis dump не светил коды).
- Каждый verify инкрементит `attempts`. Достигли лимита → ключ удаляется.

Plus rate-limit на `request_code` через ip-окно: `auth:email_req:{ip}` (counter с TTL 60).
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass

from passlib.context import CryptContext
from redis.asyncio import Redis


_CODE_KEY_TEMPLATE = "auth:email_code:{email}"
_RATE_KEY_TEMPLATE = "auth:email_req:{ip}"
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True, slots=True)
class CodeRecord:
    hash: str
    attempts: int
    requested_at: int


class CodeError(Exception):
    pass


class CodeNotFound(CodeError):
    pass


class CodeMismatch(CodeError):
    pass


class CodeLocked(CodeError):
    """Слишком много попыток — ключ удалён, нужен новый код."""


class RateLimited(CodeError):
    pass


def generate_code() -> str:
    """6-значный численный код, безопасно сгенерированный."""
    return "".join(secrets.choice("0123456789") for _ in range(6))


class EmailCodeStore:
    def __init__(
        self,
        redis: Redis,
        *,
        ttl_sec: int = 600,
        max_attempts: int = 5,
        rate_limit_per_min: int = 3,
    ) -> None:
        self._redis = redis
        self._ttl = ttl_sec
        self._max_attempts = max_attempts
        self._rate_limit = rate_limit_per_min

    @staticmethod
    def _email_key(email: str) -> str:
        return _CODE_KEY_TEMPLATE.format(email=email.strip().lower())

    @staticmethod
    def _rate_key(ip: str) -> str:
        return _RATE_KEY_TEMPLATE.format(ip=ip)

    async def check_rate_limit(self, ip: str) -> None:
        if not ip:
            return
        key = self._rate_key(ip)
        n = await self._redis.incr(key)
        if int(n) == 1:
            await self._redis.expire(key, 60)
        if int(n) > self._rate_limit:
            raise RateLimited(f"too many code requests from {ip}")

    async def issue(self, email: str) -> str:
        """Сгенерировать код, сохранить хэш в Redis, вернуть plaintext (для отправки)."""
        code = generate_code()
        record = {
            "hash": _pwd_ctx.hash(code),
            "attempts": 0,
            "requested_at": int(time.time()),
        }
        await self._redis.set(
            self._email_key(email), json.dumps(record), ex=self._ttl
        )
        return code

    async def issue_fixed(self, email: str, code: str) -> None:
        """Сохранить фиксированный код (dev mode: код известен заранее)."""
        record = {
            "hash": _pwd_ctx.hash(code),
            "attempts": 0,
            "requested_at": int(time.time()),
        }
        await self._redis.set(
            self._email_key(email), json.dumps(record), ex=self._ttl
        )

    async def verify(self, email: str, code: str) -> None:
        """Проверить код. На успех — удалить ключ. На провал — инкремент."""
        key = self._email_key(email)
        raw = await self._redis.get(key)
        if raw is None:
            raise CodeNotFound("no active code for this email")

        record = json.loads(raw)
        if not _pwd_ctx.verify(code, record["hash"]):
            record["attempts"] = int(record.get("attempts", 0)) + 1
            if record["attempts"] >= self._max_attempts:
                await self._redis.delete(key)
                raise CodeLocked("too many wrong attempts; request a new code")
            ttl = await self._redis.ttl(key)
            await self._redis.set(key, json.dumps(record), ex=max(int(ttl), 1))
            raise CodeMismatch("wrong code")

        await self._redis.delete(key)
