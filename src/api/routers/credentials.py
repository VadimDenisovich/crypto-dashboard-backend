from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CipherDep, CurrentUser, DbSession
from src.api.schemas.credential import CredentialIn, CredentialOut
from src.infrastructure.exchange_validator import CredentialValidationError
from src.repositories.credential_repo import ExchangeCredentialRepository
from src.services.credential_service import CredentialService

router = APIRouter(prefix="/api/exchange-credentials", tags=["credentials"])


@router.get("", response_model=list[CredentialOut])
async def list_credentials(user: CurrentUser, db: DbSession) -> list[CredentialOut]:
    repo = ExchangeCredentialRepository(db)
    items = await repo.list_for_user(user.id)
    return [CredentialOut.model_validate(it) for it in items]


@router.post("", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialIn, user: CurrentUser, db: DbSession, cipher: CipherDep
) -> CredentialOut:
    service = CredentialService(ExchangeCredentialRepository(db), cipher)
    try:
        cred = await service.create_for_user(
            user_id=user.id,
            exchange=body.exchange,
            label=body.label,
            api_key=body.api_key,
            api_secret=body.api_secret,
        )
    except CredentialValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return CredentialOut.model_validate(cred)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID, user: CurrentUser, db: DbSession, cipher: CipherDep
) -> None:
    service = CredentialService(ExchangeCredentialRepository(db), cipher)
    try:
        await service.delete_for_user(user_id=user.id, credential_id=credential_id)
    except CredentialValidationError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
