"""Резолв пользователя по identity-провайдеру.

Логика:
1. Ищем уже привязанный (provider, subject) → возвращаем user.
2. Если нет — пытаемся слинковать существующего user'а по email
   (когда ранее зашёл через email-code, потом подключил OAuth).
3. Иначе создаём нового user + identity.
4. Обновляем `last_login_at`.
"""

from __future__ import annotations

from src.models.user import User, UserRole
from src.repositories.oauth_identity_repo import OAuthIdentityRepository
from src.repositories.user_repo import UserRepository


class IdentityService:
    def __init__(
        self,
        users: UserRepository,
        identities: OAuthIdentityRepository,
    ) -> None:
        self._users = users
        self._identities = identities

    async def resolve_or_create(
        self, *, provider: str, subject: str, email: str | None
    ) -> User:
        existing = await self._identities.get(provider=provider, subject=subject)
        if existing is not None:
            user = await self._users.get_by_id(existing.user_id)
            if user is None:
                # Race / повреждение — создадим заново.
                user = await self._create_user(email=email or _synth_email(provider, subject))
                await self._identities.create(
                    user_id=user.id, provider=provider, subject=subject, email=email
                )
            await self._users.touch_last_login(user)
            return user

        user: User | None = None
        if email:
            user = await self._users.get_by_email(email)
        if user is None:
            user = await self._create_user(email=email or _synth_email(provider, subject))

        await self._identities.create(
            user_id=user.id, provider=provider, subject=subject, email=email
        )
        await self._users.touch_last_login(user)
        return user

    async def _create_user(self, *, email: str) -> User:
        return await self._users.create(
            email=email, password_hash=None, role=UserRole.TRADER
        )


def _synth_email(provider: str, subject: str) -> str:
    """Для провайдеров, не возвращающих email (Telegram), генерим синтетический адрес.

    Это технический address (NOT NULL constraint), пользователь его не видит.
    Вид: telegram-12345678@telegram.local — уникальность гарантирует subject.
    """
    return f"{provider}-{subject}@{provider}.local"
