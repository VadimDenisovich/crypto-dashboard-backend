from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.exchange_credential import ExchangeCredential


class ExchangeCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[ExchangeCredential]:
        result = await self._session.execute(
            select(ExchangeCredential).where(ExchangeCredential.user_id == user_id)
        )
        return result.scalars().all()

    async def get(self, cred_id: uuid.UUID) -> ExchangeCredential | None:
        return await self._session.get(ExchangeCredential, cred_id)

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        exchange: str,
        label: str,
        api_key_enc: str,
        api_secret_enc: str,
    ) -> ExchangeCredential:
        cred = ExchangeCredential(
            user_id=user_id,
            exchange=exchange,
            label=label,
            api_key_enc=api_key_enc,
            api_secret_enc=api_secret_enc,
        )
        self._session.add(cred)
        await self._session.flush()
        return cred

    async def delete(self, cred: ExchangeCredential) -> None:
        await self._session.delete(cred)
