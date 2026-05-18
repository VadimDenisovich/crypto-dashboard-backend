"""Валидация ключей биржи через ccxt.

Поднимает ccxt-клиент с переданными ключами и делает `fetch_balance` —
если биржа возвращает 401, значит ключи невалидны. Поддерживает testnet и
необязательный passphrase (для OKX / старого Coinbase Pro).
"""

from __future__ import annotations

import asyncio
from typing import Any

import ccxt

from src.infrastructure.exchange_meta import (
    SUPPORTED_EXCHANGES,
    requires_passphrase,
)


class CredentialValidationError(Exception):
    pass


def _build_client(
    exchange: str,
    api_key: str,
    api_secret: str,
    testnet: bool,
    passphrase: str | None = None,
) -> Any:
    exchange = exchange.lower()
    if exchange not in SUPPORTED_EXCHANGES:
        raise CredentialValidationError(
            f"unsupported exchange: {exchange} (supported: {sorted(SUPPORTED_EXCHANGES)})"
        )
    if not hasattr(ccxt, exchange):
        raise CredentialValidationError(f"unknown exchange: {exchange}")

    if requires_passphrase(exchange) and not passphrase:
        raise CredentialValidationError(
            f"{exchange} requires a passphrase (third secret)"
        )

    config: dict[str, Any] = {
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
    }
    if passphrase:
        config["password"] = passphrase  # ccxt использует ключ "password" для passphrase

    klass = getattr(ccxt, exchange)
    client = klass(config)
    if testnet:
        set_sandbox = getattr(client, "set_sandbox_mode", None)
        if callable(set_sandbox):
            set_sandbox(True)
    return client


def _fetch_balance_sync(client: Any) -> None:
    try:
        client.fetch_balance()
    except ccxt.AuthenticationError as exc:
        raise CredentialValidationError(f"authentication failed: {exc}") from exc
    except ccxt.NetworkError as exc:
        raise CredentialValidationError(f"network error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — surface to API as 400
        raise CredentialValidationError(f"validation failed: {exc}") from exc
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


async def validate_credentials(
    exchange: str,
    api_key: str,
    api_secret: str,
    *,
    testnet: bool = True,
    passphrase: str | None = None,
) -> None:
    client = _build_client(
        exchange, api_key, api_secret, testnet=testnet, passphrase=passphrase
    )
    await asyncio.to_thread(_fetch_balance_sync, client)
