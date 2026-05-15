"""Проверка Telegram Login Widget callback'а.

Telegram возвращает данные пользователя через JS:
{id, first_name, last_name?, username?, photo_url?, auth_date, hash}

Алгоритм проверки HMAC (https://core.telegram.org/widgets/login#checking-authorization):
1. data_check_string = "\n".join(f"{k}={v}") по всем полям кроме hash, отсортированным по ключу
2. secret = sha256(bot_token).digest()
3. expected = hmac_sha256(secret, data_check_string).hexdigest()
4. expected == hash
5. auth_date не старше N секунд
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any


class TelegramAuthError(Exception):
    pass


def verify_telegram_login(
    payload: dict[str, Any],
    *,
    bot_token: str,
    max_age_sec: int = 86400,
) -> int:
    """Проверяет HMAC и возвращает int(id) пользователя Telegram.

    Поднимает TelegramAuthError на любой провал.
    """
    if not bot_token:
        raise TelegramAuthError("server: telegram bot token not configured")

    data = dict(payload)
    received_hash = data.pop("hash", None)
    if not received_hash or not isinstance(received_hash, str):
        raise TelegramAuthError("hash field missing")

    # Только non-null поля участвуют в HMAC.
    items = sorted(
        (k, str(v)) for k, v in data.items() if v is not None and k != "hash"
    )
    data_check_string = "\n".join(f"{k}={v}" for k, v in items)
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    expected = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise TelegramAuthError("hmac mismatch")

    auth_date = int(data.get("auth_date", 0))
    if auth_date <= 0:
        raise TelegramAuthError("auth_date missing or invalid")
    if int(time.time()) - auth_date > max_age_sec:
        raise TelegramAuthError("auth_date too old")

    user_id = data.get("id")
    if user_id is None:
        raise TelegramAuthError("id missing")
    try:
        return int(user_id)
    except (TypeError, ValueError) as exc:
        raise TelegramAuthError("id is not numeric") from exc
