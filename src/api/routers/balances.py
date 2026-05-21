from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request, status

from src.api.deps import CurrentUser, DbSession, get_redis
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

    currencies_map: dict[uuid.UUID, dict[str, BalanceOut]] = {}
    last_observed: datetime | None = None

    for cred in creds:
        items = await BalanceRepository(db).latest_for_credential(cred.id)
        if not items:
            continue
        per_cred: dict[str, BalanceOut] = {}
        for b in items:
            bal = BalanceOut.model_validate(b)
            # Дедупликация по валюте: берём только самый свежий снапшот для каждой валюты
            if bal.currency not in per_cred:
                per_cred[bal.currency] = bal
            if last_observed is None or bal.observed_at > last_observed:
                last_observed = bal.observed_at
        currencies_map[cred.id] = per_cred

    all_balances: list[BalanceOut] = []
    total_free = Decimal("0")
    total_used = Decimal("0")
    open_pnl = Decimal("0")
    position_count = 0

    for cred_id, per_cred in currencies_map.items():
        for bal in per_cred.values():
            all_balances.append(bal)
            total_free += bal.free
            total_used += bal.used

        positions = await PositionRepository(db).latest_for_credential(cred_id)
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
        last_observed_at=last_observed,
    )


@router.get("/balances/debug")
async def balances_debug(user: CurrentUser, db: DbSession, request: Request) -> dict:
    """Диагностика: показывает все балансовые снапшоты, credentials, и статус engine."""
    creds = await ExchangeCredentialRepository(db).list_for_user(user.id)
    result: dict = {
        "credentials_count": len(creds),
        "credentials": [{"id": str(c.id), "exchange": c.exchange, "label": c.label} for c in creds],
        "balance_snapshots": [],
        "engine_alive": None,
    }

    for cred in creds:
        items = await BalanceRepository(db).latest_for_credential(cred.id)
        result["balance_snapshots"].append({
            "credential_id": str(cred.id),
            "snapshot_count": len(items),
            "latest": [BalanceOut.model_validate(b).model_dump(mode="json") for b in items[:10]],
        })

    # Проверяем heartbeat engine через Redis
    try:
        redis = get_redis(request)
        hb = await redis.get("engine:last_heartbeat")
        result["engine_alive"] = hb is not None
        if hb:
            result["engine_last_heartbeat"] = hb if isinstance(hb, str) else hb.decode()
    except Exception:
        result["engine_alive"] = None  # Redis не доступен

    return result


@router.get("/engine-health", include_in_schema=False)
async def engine_health(request: Request) -> dict:
    """Публичный эндпоинт: жив ли engine (есть ли heartbeat) + ошибки баланса."""
    redis = get_redis(request)
    hb = await redis.get("engine:last_heartbeat")
    err_raw = await redis.get("engine:last_balance_error")
    err: dict | None = None
    if err_raw:
        import json as _json
        err = _json.loads(err_raw) if isinstance(err_raw, str) else _json.loads(err_raw.decode())
    return {
        "engine_alive": hb is not None,
        "last_heartbeat": hb if isinstance(hb, (str, bytes)) and hb else None,
        "last_balance_error": err,
    }
