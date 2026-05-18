"""Cloudflare Turnstile verification.

Бэк дёргает https://challenges.cloudflare.com/turnstile/v0/siteverify
с секретом и user-токеном. В dev/CI можно отключить через `BACKEND_CAPTCHA_DISABLED=true`.

История: до Phase 3 использовался hCaptcha (api.hcaptcha.com/siteverify). API формат
у обоих одинаковый (поля secret/response/remoteip + JSON-ответ с `success`), поэтому
смена сводится к одной строке URL'а.
"""

from __future__ import annotations

import httpx

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TIMEOUT_SEC = 5.0


class CaptchaError(Exception):
    pass


async def verify_turnstile(
    *,
    secret: str,
    token: str,
    remoteip: str | None = None,
    disabled: bool = False,
) -> None:
    if disabled:
        return
    if not token:
        raise CaptchaError("captcha token missing")
    if not secret:
        raise CaptchaError("Turnstile secret not configured on server")

    data = {"secret": secret, "response": token}
    if remoteip:
        data["remoteip"] = remoteip

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SEC) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=data)
    except httpx.HTTPError as exc:
        raise CaptchaError(f"Turnstile verification network error: {exc}") from exc

    if resp.status_code != 200:
        raise CaptchaError(f"Turnstile verification HTTP {resp.status_code}")

    body = resp.json()
    if not body.get("success"):
        codes = body.get("error-codes") or []
        raise CaptchaError(f"Turnstile rejected: {','.join(codes) or 'unknown'}")


# Алиас для обратной совместимости — на один коммит, потом удалим.
verify_hcaptcha = verify_turnstile
