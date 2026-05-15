"""hCaptcha verification.

Бэк дёргает https://api.hcaptcha.com/siteverify с секретом и user-токеном.
В dev/CI можно отключить через `BACKEND_CAPTCHA_DISABLED=true`.
"""

from __future__ import annotations

import httpx

HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"
_TIMEOUT_SEC = 5.0


class CaptchaError(Exception):
    pass


async def verify_hcaptcha(
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
        raise CaptchaError("hCaptcha secret not configured on server")

    data = {"secret": secret, "response": token}
    if remoteip:
        data["remoteip"] = remoteip

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SEC) as client:
            resp = await client.post(HCAPTCHA_VERIFY_URL, data=data)
    except httpx.HTTPError as exc:
        raise CaptchaError(f"hCaptcha verification network error: {exc}") from exc

    if resp.status_code != 200:
        raise CaptchaError(f"hCaptcha verification HTTP {resp.status_code}")

    body = resp.json()
    if not body.get("success"):
        codes = body.get("error-codes") or []
        raise CaptchaError(f"hCaptcha rejected: {','.join(codes) or 'unknown'}")
