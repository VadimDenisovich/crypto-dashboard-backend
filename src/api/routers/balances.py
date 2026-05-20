from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser, DbSession
from src.api.schemas.market import BalanceOut, BalanceSummaryOut
from src.repositories.balance_repo import BalanceRepository
from src.repositories.credential_repo import ExchangeCredentialRepository
from src.repositories.position_repo import PositionRepository

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


@router.get("/balances/summary", response_model=BalanceSummaryOut)
async def balances_summary(user: CurrentUser, db: DbSession) -> BalanceSummaryOut:
    creds = await ExchangeCredentialRepository(db).list_for_user(user.id)
    if not creds:
        return BalanceSummaryOut(
            total_equity=Decimal("0"),
            free_total=Decimal("0"),
            used_total=Decimal("0"),
            currencies=[],
        )

    all_balances: list[BalanceOut] = []
    total_free = Decimal("0")
    total_used = Decimal("0")
    open_pnl = Decimal("0")
    position_count = 0

    for cred in creds:
        items = await BalanceRepository(db).latest_for_credential(cred.id)
        for b in items:
            bal = BalanceOut.model_validate(b)
            all_balances.append(bal)
            total_free += bal.free
            total_used += bal.used

        positions = await PositionRepository(db).latest_for_credential(cred.id)
        for p in positions:
            position_count += 1
            open_pnl += p.current_pnl

    return BalanceSummaryOut(
        total_equity=total_free + total_used,
        free_total=total_free,
        used_total=total_used,
        currencies=all_balances,
        open_pnl=open_pnl,
        position_count=position_count,
    )
