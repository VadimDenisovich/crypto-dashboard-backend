from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.oauth_identity import OAuthIdentity


class OAuthIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, provider: str, subject: str) -> OAuthIdentity | None:
        result = await self._session.execute(
            select(OAuthIdentity).where(
                OAuthIdentity.provider == provider, OAuthIdentity.subject == subject
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, *, user_id: uuid.UUID, provider: str, subject: str, email: str | None
    ) -> OAuthIdentity:
        identity = OAuthIdentity(
            user_id=user_id, provider=provider, subject=subject, email=email
        )
        self._session.add(identity)
        await self._session.flush()
        return identity
