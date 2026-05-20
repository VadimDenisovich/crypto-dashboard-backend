from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from src.api.deps import get_redis
from src.infrastructure.exchange_meta import SUPPORTED_EXCHANGES

router = APIRouter(prefix="/api/candles", tags=["candles"])

_CANDLES_CACHE_KEY = "candles:{exchange}:{symbol}:{timeframe}"
_CANDLES_CACHE_TTL_SEC = 60
_TIMEFRAME_RE = re.compile(r"^\d+[mhdwM]$")


@router.get("/{exchange}/{symbol:path}")
async def get_candles(
    request: Request,
    exchange: str = Path(..., min_length=1, max_length=32),
    symbol: str = Path(..., min_length=3, max_length=64),
    limit: int = Query(100),
) -> list[dict]:
    parts = symbol.rsplit("/", 1)
    if len(parts) != 2 or not _TIMEFRAME_RE.match(parts[1]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "expected /{exchange}/{base}/{quote}/{timeframe}",
        )
    pair, timeframe = parts

    exchange_lc = exchange.lower()
    if exchange_lc not in SUPPORTED_EXCHANGES:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"exchange '{exchange}' not supported"
        )

    redis = get_redis(request)
    key = _CANDLES_CACHE_KEY.format(exchange=exchange_lc, symbol=pair, timeframe=timeframe)
    cached = await redis.get(key)
    if cached:
        return list(json.loads(cached))

    import ccxt.async_support as ccxt_async

    klass = getattr(ccxt_async, exchange_lc, None)
    if klass is None:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"no ccxt client for {exchange_lc}"
        )

    client = klass({"enableRateLimit": True})
    try:
        raw = await client.fetch_ohlcv(pair, timeframe, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"failed to fetch candles: {exc}"
        ) from exc
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                await close()
            except Exception:
                pass

    candles = [
        {
            "timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
            "open": str(o),
            "high": str(h),
            "low": str(l),
            "close": str(c),
            "volume": str(v),
        }
        for ts, o, h, l, c, v in raw
    ]

    await redis.set(key, json.dumps(candles), ex=_CANDLES_CACHE_TTL_SEC)
    return candles
