from __future__ import annotations

import uuid

import pyotp
from redis.asyncio import Redis

from src.models.user import User
from src.repositories.user_repo import UserRepository


class TwoFaError(Exception):
    """Бизнес-ошибки 2FA (нет setup, неверный код, не включено)."""


_ISSUER = "Crypto Dashboard"
_SETUP_TTL_SEC = 300  # 5 минут на сканирование и ввод первого кода


def _setup_key(user_id: uuid.UUID) -> str:
    return f"2fa_setup:{user_id}"


class TwoFaService:
    def __init__(self, user_repo: UserRepository, redis: Redis) -> None:
        self._users = user_repo
        self._redis = redis

    async def setup(self, *, user: User) -> str:
        """Генерирует новый TOTP-секрет и сохраняет его в Redis на 5 мин.

        Возвращает otpauth:// URI — фронт рисует QR-код по нему. Секрет в БД
        записываем только после успешной верификации первого кода (метод
        `verify`), чтобы случайное недосканированное состояние не выключало
        старую 2FA, если она была включена.
        """
        secret = pyotp.random_base32()
        await self._redis.set(
            _setup_key(user.id), secret, ex=_SETUP_TTL_SEC
        )
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name=_ISSUER
        )
        return uri

    async def verify(self, *, user: User, code: str) -> None:
        """Подтверждает setup. При успехе пишет секрет в users, ставит флаг."""
        raw = await self._redis.get(_setup_key(user.id))
        if raw is None:
            raise TwoFaError("setup not started or expired")
        secret = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        # valid_window=1 — допускаем ±30 сек для джет-лега часов на устройстве.
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise TwoFaError("invalid code")
        user.two_fa_secret = secret
        user.two_fa_enabled = True
        await self._users.flush()
        await self._redis.delete(_setup_key(user.id))

    async def disable(self, *, user: User) -> None:
        user.two_fa_secret = None
        user.two_fa_enabled = False
        await self._users.flush()
        await self._redis.delete(_setup_key(user.id))
