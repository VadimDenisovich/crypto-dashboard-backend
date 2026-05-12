from __future__ import annotations

import asyncio
from typing import Any

import ccxt


class CredentialValidationError(Exception):
    pass


def _build_client(exchange: str, api_key: str, api_secret: str, testnet: bool) -> Any:
    exchange = exchange.lower()
    if not hasattr(ccxt, exchange):
        raise CredentialValidationError(f"unknown exchange: {exchange}")
    klass = getattr(ccxt, exchange)
    client = klass({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})
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
    exchange: str, api_key: str, api_secret: str, *, testnet: bool = True
) -> None:
    client = _build_client(exchange, api_key, api_secret, testnet=testnet)
    await asyncio.to_thread(_fetch_balance_sync, client)
