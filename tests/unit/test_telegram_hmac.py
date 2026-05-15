from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from src.infrastructure.telegram_auth import TelegramAuthError, verify_telegram_login


_BOT_TOKEN = "123:ABC-fake-bot-token"


def _sign(payload: dict[str, object]) -> str:
    items = sorted((k, str(v)) for k, v in payload.items() if v is not None and k != "hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in items)
    secret = hashlib.sha256(_BOT_TOKEN.encode("utf-8")).digest()
    return hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


def _payload(**overrides):
    base = {
        "id": 12345,
        "first_name": "Vadim",
        "last_name": None,
        "username": "vadik",
        "photo_url": None,
        "auth_date": int(time.time()),
    }
    base.update(overrides)
    return base


def test_valid_signature_returns_id() -> None:
    p = _payload()
    p["hash"] = _sign(p)
    assert verify_telegram_login(p, bot_token=_BOT_TOKEN) == 12345


def test_wrong_hash_rejected() -> None:
    p = _payload()
    p["hash"] = "deadbeef" * 8
    with pytest.raises(TelegramAuthError, match="hmac mismatch"):
        verify_telegram_login(p, bot_token=_BOT_TOKEN)


def test_old_auth_date_rejected() -> None:
    p = _payload(auth_date=int(time.time()) - 100_000)
    p["hash"] = _sign(p)
    with pytest.raises(TelegramAuthError, match="too old"):
        verify_telegram_login(p, bot_token=_BOT_TOKEN, max_age_sec=3600)


def test_missing_hash_rejected() -> None:
    with pytest.raises(TelegramAuthError, match="hash field"):
        verify_telegram_login(_payload(), bot_token=_BOT_TOKEN)


def test_missing_bot_token_rejected() -> None:
    with pytest.raises(TelegramAuthError, match="not configured"):
        verify_telegram_login({"id": 1, "auth_date": 1, "hash": "x"}, bot_token="")


def test_extra_fields_dont_break_signature() -> None:
    p = _payload(first_name="Иван", username="ivan_test")
    p["hash"] = _sign(p)
    assert verify_telegram_login(p, bot_token=_BOT_TOKEN) == 12345
