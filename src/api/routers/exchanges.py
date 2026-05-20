"""Публичные endpoint'ы для UI-каталога бирж и торговых пар.

- GET /api/exchanges/supported — список бирж и их особенности (для формы Settings).
- GET /api/exchanges/{name}/symbols — топ USDT-пар по объёму, кэш 1 час в Redis.

Public endpoints (без авторизации) — это публичные данные биржи.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Path, Request, status
from pydantic import BaseModel

from src.api.deps import get_redis
from src.infrastructure.exchange_meta import (
    ALLOWED_SYMBOLS,
    SUPPORTED_EXCHANGES,
    all_metas,
)

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])

# Бамп версии ключа, чтобы старый кэш топ-10 пар не подмешивался после ограничения.
_SYMBOLS_CACHE_KEY = "exchanges:symbols:v2:{name}"
_SYMBOLS_CACHE_TTL_SEC = 3600


class ExchangeMetaOut(BaseModel):
    name: str
    display_name: str
    requires_passphrase: bool
    supports_testnet: bool


@router.get("/supported", response_model=list[ExchangeMetaOut])
async def list_supported() -> list[ExchangeMetaOut]:
    # asdict() работает с slots-dataclass, в отличие от .__dict__.
    return [ExchangeMetaOut(**asdict(m)) for m in all_metas()]


@router.get("/{name}/symbols", response_model=list[str])
async def list_symbols(
    request: Request,
    name: str = Path(..., min_length=1, max_length=32),
) -> list[str]:
    name_lc = name.lower()
    if name_lc not in SUPPORTED_EXCHANGES:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"exchange '{name}' not supported"
        )

    redis = get_redis(request)
    key = _SYMBOLS_CACHE_KEY.format(name=name_lc)
    cached = await redis.get(key)
    if cached:
        return list(json.loads(cached))

    try:
        symbols = await _fetch_top_symbols(name_lc)
    except Exception as exc:  # noqa: BLE001 — сетевая ошибка биржи / ccxt
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"failed to load symbols: {exc}"
        ) from exc

    await redis.set(key, json.dumps(symbols), ex=_SYMBOLS_CACHE_TTL_SEC)
    return symbols


async def _fetch_top_symbols(exchange_name: str) -> list[str]:
    """Возвращает разрешённые пары (ALLOWED_SYMBOLS), реально доступные на бирже.

    Пересекаем фиксированный allowlist с активными markets биржи (сохраняя порядок
    allowlist). Если markets загрузить не удалось — отдаём весь allowlist как fallback.
    """
    import ccxt.async_support as ccxt_async  # импорт здесь — модуль тяжёлый

    klass = getattr(ccxt_async, exchange_name, None)
    if klass is None:
        raise RuntimeError(f"ccxt has no async client for {exchange_name}")

    client = klass({"enableRateLimit": True})
    try:
        markets = await client.load_markets()
        available = {
            sym
            for sym, info in markets.items()
            if info.get("active", True)
        }
        return [s for s in ALLOWED_SYMBOLS if s in available]
    except Exception:
        # Биржа недоступна / load_markets упал — не блокируем UI, отдаём allowlist.
        return list(ALLOWED_SYMBOLS)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                await close()
            except Exception:
                pass
