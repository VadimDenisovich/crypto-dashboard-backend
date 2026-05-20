from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser, DbSession
from src.api.schemas.market import PositionOut
from src.repositories.credential_repo import ExchangeCredentialRepository
from src.repositories.position_repo import PositionRepository

router = APIRouter(prefix="/api", tags=["positions"])


@router.get("/positions", response_model=list[PositionOut])
async def list_positions(
    user: CurrentUser, db: DbSession, credential_id: uuid.UUID = Query(...)
) -> list[PositionOut]:
    cred = await ExchangeCredentialRepository(db).get(credential_id)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    if cred.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "credential not owned")
    items = await PositionRepository(db).latest_for_credential(credential_id)
    return [PositionOut.model_validate(p) for p in items]
