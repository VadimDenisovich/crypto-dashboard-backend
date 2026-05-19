"""Валидация ключей биржи через ccxt.

Поднимает async ccxt-клиент с переданными ключами и делает `fetch_balance` —
если биржа возвращает 401, значит ключи невалидны. Поддерживает testnet и
необязательный passphrase (для OKX / старого Coinbase Pro).

Перешли с sync `ccxt.binance` (через `asyncio.to_thread`) на
`ccxt.async_support.binance` — это даёт настоящую async-обвязку через aiohttp,
лучшие сообщения об ошибках и более предсказуемые таймауты.
"""

from __future__ import annotations

import logging
from typing import Any

import ccxt.async_support as ccxt_async

from src.infrastructure.exchange_meta import (
    SUPPORTED_EXCHANGES,
    requires_passphrase,
)

logger = logging.getLogger(__name__)

# 30 секунд — на VPS с медленным egress 10s по умолчанию мало.
_HTTP_TIMEOUT_MS = 30_000


class CredentialValidationError(Exception):
    pass


def _build_async_client(
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
    if not hasattr(ccxt_async, exchange):
        raise CredentialValidationError(f"unknown exchange: {exchange}")

    if requires_passphrase(exchange) and not passphrase:
        raise CredentialValidationError(
            f"{exchange} requires a passphrase (third secret)"
        )

    config: dict[str, Any] = {
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "timeout": _HTTP_TIMEOUT_MS,
    }
    if passphrase:
        config["password"] = passphrase  # ccxt использует ключ "password" для passphrase

    klass = getattr(ccxt_async, exchange)
    client = klass(config)
    if testnet:
        set_sandbox = getattr(client, "set_sandbox_mode", None)
        if callable(set_sandbox):
            set_sandbox(True)
    return client


def _friendly_network_error(exchange_id: str) -> str:
    return (
        f"Не удалось связаться с биржей {exchange_id} (testnet). "
        "Возможно, сервис временно недоступен или firewall блокирует соединение. "
        "Попробуйте позже или другую биржу."
    )


async def validate_credentials(
    exchange: str,
    api_key: str,
    api_secret: str,
    *,
    testnet: bool = True,
    passphrase: str | None = None,
) -> None:
    client = _build_async_client(
        exchange, api_key, api_secret, testnet=testnet, passphrase=passphrase
    )
    try:
        await client.fetch_balance()
    except ccxt_async.AuthenticationError as exc:
        logger.warning(
            "exchange.auth_failed",
            extra={"exchange": client.id, "err": repr(exc)},
        )
        raise CredentialValidationError(
            f"Биржа отклонила ключ: {exc}"
        ) from exc
    except ccxt_async.NetworkError as exc:
        # ccxt прячет underlying cause — логируем traceback и repr(__cause__),
        # чтобы в логах было видно реальный DNS/Timeout/SSL.
        logger.exception(
            "exchange.network_error",
            extra={
                "exchange": client.id,
                "err": repr(exc),
                "cause": repr(getattr(exc, "__cause__", None)),
            },
        )
        raise CredentialValidationError(
            _friendly_network_error(client.id)
        ) from exc
    except Exception as exc:
        logger.exception("exchange.validate_failed", extra={"exchange": client.id})
        raise CredentialValidationError(f"Ошибка валидации: {exc}") from exc
    finally:
        try:
            await client.close()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass
