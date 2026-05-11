from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser, DbSession
from src.api.schemas.market import BalanceOut
from src.repositories.balance_repo import BalanceRepository
from src.repositories.credential_repo import ExchangeCredentialRepository

router = APIRouter(prefix="/api", tags=["balances"])


@router.get("/balances", response_model=list[BalanceOut])
async def list_balances(
    user: CurrentUser, db: DbSession, credential_id: uuid.UUID = Query(...)
) -> list[BalanceOut]:
    cred = await ExchangeCredentialRepository(db).get(credential_id)
    if cred is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "credential not found")
    if cred.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "credential not owned")
    items = await BalanceRepository(db).latest_for_credential(credential_id)
    return [BalanceOut.model_validate(b) for b in items]
