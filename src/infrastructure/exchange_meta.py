"""Метаданные поддерживаемых бирж — единый источник правды для бэка и фронта.

Используется:
- exchange_validator.py — проверить allowed + passphrase requirement
- routers/exchanges.py — отдать фронту через GET /api/exchanges/supported
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExchangeMeta:
    name: str            # ccxt-id (lowercase, как `ccxt.binance`)
    display_name: str    # человекочитаемое имя для UI
    requires_passphrase: bool
    supports_testnet: bool


_REGISTRY: tuple[ExchangeMeta, ...] = (
    ExchangeMeta(
        name="binance",
        display_name="Binance",
        requires_passphrase=False,
        supports_testnet=True,
    ),
    ExchangeMeta(
        name="bybit",
        display_name="Bybit",
        requires_passphrase=False,
        supports_testnet=True,
    ),
    ExchangeMeta(
        name="okx",
        display_name="OKX",
        requires_passphrase=True,   # OKX обязательно требует passphrase
        supports_testnet=True,
    ),
    ExchangeMeta(
        name="mexc",
        display_name="MEXC",
        requires_passphrase=False,
        supports_testnet=True,
    ),
)


SUPPORTED_EXCHANGES: frozenset[str] = frozenset(m.name for m in _REGISTRY)


def all_metas() -> list[ExchangeMeta]:
    return list(_REGISTRY)


def get_meta(name: str) -> ExchangeMeta | None:
    name_lc = name.lower()
    for m in _REGISTRY:
        if m.name == name_lc:
            return m
    return None


def requires_passphrase(name: str) -> bool:
    m = get_meta(name)
    return m.requires_passphrase if m else False
