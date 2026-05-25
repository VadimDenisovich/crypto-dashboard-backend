from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from redis.asyncio import Redis

from src.infrastructure.exchange_meta import ALLOWED_SYMBOLS, SUPPORTED_EXCHANGES
from src.logging_setup import get_logger

log = get_logger(__name__)

_PRICE_CACHE_KEY = "prices:usdt:{exchange}:{currency}"
_PRICE_CACHE_TTL_SEC = 60
_USDT = "USDT"
_VALUED_BASES = frozenset(symbol.split("/", 1)[0] for symbol in ALLOWED_SYMBOLS)


async def get_usdt_price(
    redis: Redis,
    *,
    exchange: str,
    currency: str,
) -> Decimal | None:
    currency_norm = currency.upper()
    if currency_norm == _USDT:
        return Decimal("1")
    if currency_norm not in _VALUED_BASES:
        return None

    exchange_norm = exchange.lower()
    key = _PRICE_CACHE_KEY.format(exchange=exchange_norm, currency=currency_norm)
    cached = await redis.get(key)
    if cached:
        try:
            raw_cached = cached.decode() if isinstance(cached, bytes) else str(cached)
            return Decimal(raw_cached)
        except (InvalidOperation, UnicodeDecodeError):
            pass

    price = await _fetch_usdt_price(exchange_norm, currency_norm)
    if price is None and exchange_norm != "binance":
        price = await _fetch_usdt_price("binance", currency_norm)
    if price is None:
        return None

    await redis.set(key, str(price), ex=_PRICE_CACHE_TTL_SEC)
    return price


async def _fetch_usdt_price(exchange: str, currency: str) -> Decimal | None:
    if exchange not in SUPPORTED_EXCHANGES:
        return None

    symbol = f"{currency}/{_USDT}"
    try:
        return await _fetch_ticker_last(exchange, symbol)
    except Exception as exc:
        log.warning(
            "balance_valuation.price_fetch_failed",
            exchange=exchange,
            symbol=symbol,
            error=str(exc),
        )
        return None


async def _fetch_ticker_last(exchange: str, symbol: str) -> Decimal | None:
    import ccxt.async_support as ccxt_async  # type: ignore[import-untyped]

    klass = getattr(ccxt_async, exchange, None)
    if klass is None:
        return None

    client = klass({"enableRateLimit": True})
    try:
        ticker: dict[str, Any] = await client.fetch_ticker(symbol)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                await close()
            except Exception:
                pass

    raw_price = (
        ticker.get("last")
        or ticker.get("close")
        or ticker.get("bid")
        or ticker.get("ask")
    )
    if raw_price is None:
        return None
    price = Decimal(str(raw_price))
    return price if price > 0 else None
