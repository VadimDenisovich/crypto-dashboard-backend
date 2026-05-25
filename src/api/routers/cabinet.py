from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis

from src.api.deps import CurrentUser, DbSession, get_redis
from src.api.schemas.cabinet import (
    ApiKeyCreateIn,
    ApiKeyCreateOut,
    ApiKeyOut,
    TwoFaSetupOut,
    TwoFaStateOut,
    TwoFaVerifyIn,
)
from src.repositories.api_key_repo import UserApiKeyRepository
from src.repositories.user_repo import UserRepository
from src.services.api_key_service import ApiKeyError, ApiKeyService
from src.services.two_fa_service import TwoFaError, TwoFaService

router = APIRouter(prefix="/api/cabinet", tags=["cabinet"])

RedisDep = Annotated[Redis, Depends(get_redis)]


# ── API keys ────────────────────────────────────────────────────────────────


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(user: CurrentUser, db: DbSession) -> list[ApiKeyOut]:
    repo = UserApiKeyRepository(db)
    items = await repo.list_for_user(user.id)
    return [ApiKeyOut.model_validate(it) for it in items]


@router.post(
    "/api-keys", response_model=ApiKeyCreateOut, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    body: ApiKeyCreateIn, user: CurrentUser, db: DbSession
) -> ApiKeyCreateOut:
    service = ApiKeyService(UserApiKeyRepository(db))
    item, secret = await service.generate(user_id=user.id, label=body.label)
    return ApiKeyCreateOut(
        id=item.id,
        label=item.label,
        key_prefix=item.key_prefix,
        created_at=item.created_at,
        key=secret,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    service = ApiKeyService(UserApiKeyRepository(db))
    try:
        await service.delete_for_user(user_id=user.id, key_id=key_id)
    except ApiKeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


# ── 2FA ─────────────────────────────────────────────────────────────────────


@router.get("/2fa", response_model=TwoFaStateOut)
async def get_two_fa(user: CurrentUser) -> TwoFaStateOut:
    return TwoFaStateOut(enabled=user.two_fa_enabled)


@router.post("/2fa/setup", response_model=TwoFaSetupOut)
async def setup_two_fa(
    user: CurrentUser, db: DbSession, redis: RedisDep
) -> TwoFaSetupOut:
    service = TwoFaService(UserRepository(db), redis)
    uri = await service.setup(user=user)
    return TwoFaSetupOut(otpauth_uri=uri)


@router.post("/2fa/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_two_fa(
    body: TwoFaVerifyIn, user: CurrentUser, db: DbSession, redis: RedisDep
) -> None:
    service = TwoFaService(UserRepository(db), redis)
    try:
        await service.verify(user=user, code=body.code)
    except TwoFaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.delete("/2fa", status_code=status.HTTP_204_NO_CONTENT)
async def disable_two_fa(
    user: CurrentUser, db: DbSession, redis: RedisDep
) -> None:
    service = TwoFaService(UserRepository(db), redis)
    await service.disable(user=user)
