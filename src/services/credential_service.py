from __future__ import annotations

import uuid

from src.infrastructure.crypto import Cipher
from src.infrastructure.exchange_validator import (
    CredentialValidationError,
    validate_credentials,
)
from src.models.exchange_credential import ExchangeCredential
from src.repositories.credential_repo import ExchangeCredentialRepository


class CredentialService:
    def __init__(self, repo: ExchangeCredentialRepository, cipher: Cipher) -> None:
        self._repo = repo
        self._cipher = cipher

    async def create_for_user(
        self,
        *,
        user_id: uuid.UUID,
        exchange: str,
        label: str,
        api_key: str,
        api_secret: str,
    ) -> ExchangeCredential:
        # 1. Валидируем ключи через биржу до сохранения.
        await validate_credentials(exchange, api_key, api_secret)
        # 2. Шифруем и сохраняем.
        return await self._repo.create(
            user_id=user_id,
            exchange=exchange,
            label=label,
            api_key_enc=self._cipher.encrypt(api_key),
            api_secret_enc=self._cipher.encrypt(api_secret),
        )

    async def delete_for_user(
        self, *, user_id: uuid.UUID, credential_id: uuid.UUID
    ) -> None:
        cred = await self._repo.get(credential_id)
        if cred is None or cred.user_id != user_id:
            raise CredentialValidationError("credential not found")
        await self._repo.delete(cred)
