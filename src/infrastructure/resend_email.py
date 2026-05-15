"""Resend (https://resend.com) — отправка транзакционных email.

Тонкий клиент через httpx. Без SDK, потому что нам нужен один endpoint:
POST https://api.resend.com/emails.
"""

from __future__ import annotations

import httpx

RESEND_API_URL = "https://api.resend.com/emails"
_TIMEOUT_SEC = 10.0


class ResendError(Exception):
    pass


class ResendClient:
    def __init__(
        self,
        *,
        api_key: str,
        sender_email: str,
        sender_name: str = "Crypto Dashboard",
    ) -> None:
        self._api_key = api_key
        self._sender_email = sender_email
        self._sender_name = sender_name

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._sender_email)

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> str:
        if not self.configured:
            raise ResendError("Resend is not configured (API key or sender missing)")

        from_addr = (
            f"{self._sender_name} <{self._sender_email}>"
            if self._sender_name
            else self._sender_email
        )
        payload: dict[str, str | list[str]] = {
            "from": from_addr,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            payload["text"] = text

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SEC) as client:
                resp = await client.post(
                    RESEND_API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except httpx.HTTPError as exc:
            raise ResendError(f"resend network error: {exc}") from exc

        if resp.status_code >= 300:
            raise ResendError(f"resend HTTP {resp.status_code}: {resp.text[:300]}")

        return str(resp.json().get("id", ""))


def build_code_email(code: str) -> tuple[str, str, str]:
    """Возвращает (subject, html, text) для письма с одноразовым кодом."""
    subject = f"Crypto Dashboard — код входа: {code}"
    text = (
        f"Ваш код входа: {code}\n\n"
        "Код действует 10 минут. Если вы не запрашивали вход, проигнорируйте это письмо."
    )
    html = f"""
    <!doctype html>
    <html>
      <body style="font-family: -apple-system, Segoe UI, sans-serif; background:#0b0e14; color:#f8fafc; padding:40px;">
        <table role="presentation" width="100%" style="max-width: 480px; margin: 0 auto; background:#1e222d; border:1px solid #2a2e39; border-radius:12px; padding:32px;">
          <tr>
            <td>
              <h1 style="margin:0 0 8px; font-size:22px; font-weight:600;">Crypto Dashboard</h1>
              <p style="margin:0 0 24px; color:#94a3b8; font-size:14px;">Код для входа</p>
              <div style="background:#0b0e14; border:1px solid #2a2e39; border-radius:8px; padding:18px; text-align:center; font-size:32px; letter-spacing:10px; font-weight:700;">
                {code}
              </div>
              <p style="margin:24px 0 0; color:#94a3b8; font-size:13px; line-height:1.5;">
                Код действует 10 минут. Если вы не запрашивали вход — просто проигнорируйте это письмо.
              </p>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """.strip()
    return subject, html, text
