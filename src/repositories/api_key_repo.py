from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user_api_key import UserApiKey


class UserApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[UserApiKey]:
        result = await self._session.execute(
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id)
            .order_by(UserApiKey.created_at.desc())
        )
        return result.scalars().all()

    async def get(self, key_id: uuid.UUID) -> UserApiKey | None:
        return await self._session.get(UserApiKey, key_id)

    async def get_by_prefix(self, prefix: str) -> UserApiKey | None:
        result = await self._session.execute(
            select(UserApiKey).where(UserApiKey.key_prefix == prefix)
        )
        return result.scalars().first()

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        label: str,
        key_prefix: str,
        key_hash: str,
    ) -> UserApiKey:
        item = UserApiKey(
            user_id=user_id,
            label=label,
            key_prefix=key_prefix,
            key_hash=key_hash,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def delete(self, item: UserApiKey) -> None:
        await self._session.delete(item)
