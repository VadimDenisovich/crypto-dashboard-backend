from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

import bcrypt

from src.models.user_api_key import UserApiKey
from src.repositories.api_key_repo import UserApiKeyRepository


class ApiKeyError(Exception):
    """Бизнес-ошибка операций с API ключом (не найдено, чужой ключ и т.п.)."""


# Префикс в открытом виде позволяет O(1) поиск по индексу при верификации;
# далее всё ещё проверяем bcrypt-хеш полного секрета.
_KEY_PREFIX_LEN = 12


def _generate_key() -> tuple[str, str, str]:
    """Возвращает (secret, prefix, hash). Секрет нигде не сохраняется."""
    # `cd_` — фирменный префикс, отличает наш ключ от чужих токенов в логах.
    secret = "cd_" + secrets.token_hex(16)  # 35 chars total
    prefix = secret[:_KEY_PREFIX_LEN]
    hashed = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return secret, prefix, hashed


class ApiKeyService:
    def __init__(self, repo: UserApiKeyRepository) -> None:
        self._repo = repo

    async def generate(
        self, *, user_id: uuid.UUID, label: str | None
    ) -> tuple[UserApiKey, str]:
        """Создаёт ключ. Вернёт пару (db-объект, полный секрет)."""
        secret, prefix, hashed = _generate_key()
        item = await self._repo.create(
            user_id=user_id,
            label=(label or "").strip() or f"Ключ от {datetime.now(timezone.utc):%d.%m.%Y}",
            key_prefix=prefix,
            key_hash=hashed,
        )
        return item, secret

    async def delete_for_user(
        self, *, user_id: uuid.UUID, key_id: uuid.UUID
    ) -> None:
        item = await self._repo.get(key_id)
        if item is None or item.user_id != user_id:
            raise ApiKeyError("api key not found")
        await self._repo.delete(item)

    async def verify(self, secret: str) -> UserApiKey | None:
        """Находит ключ по префиксу и проверяет полный bcrypt-хеш.

        Возвращает запись `UserApiKey` либо None. Используется на внешнем
        эндпоинте, который не имеет JWT-аутентификации.
        """
        if not secret or len(secret) < _KEY_PREFIX_LEN:
            return None
        prefix = secret[:_KEY_PREFIX_LEN]
        item = await self._repo.get_by_prefix(prefix)
        if item is None:
            return None
        try:
            ok = bcrypt.checkpw(secret.encode("utf-8"), item.key_hash.encode("utf-8"))
        except ValueError:
            return None
        return item if ok else None
