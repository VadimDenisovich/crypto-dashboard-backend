"""Email + 6-значный код — flow auth-сервиса.

request_code:
    captcha → rate-limit → issue code → отправка через Resend
verify_code:
    проверка кода → resolve/create user → выдача JWT
"""

from __future__ import annotations

from src.config import Settings
from src.infrastructure.captcha import verify_turnstile
from src.infrastructure.email_codes import EmailCodeStore
from src.infrastructure.resend_email import ResendClient, build_code_email
from src.models.user import User, UserRole
from src.repositories.user_repo import UserRepository
from src.services.auth_service import AuthService, TokenPair


class EmailAuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        codes: EmailCodeStore,
        resend: ResendClient,
        users: UserRepository,
        auth: AuthService,
    ) -> None:
        self._settings = settings
        self._codes = codes
        self._resend = resend
        self._users = users
        self._auth = auth

    async def request_code(
        self, *, email: str, captcha_token: str, remoteip: str | None
    ) -> None:
        # Dev mode: пропускаем капчу, генерим код "000000", не отправляем email.
        if self._settings.backend_dev_mode:
            await self._codes.issue_fixed(email, "000000")
            return

        # Turnstile-секрет основной, hcaptcha-fallback для backwards-compat — Phase 2.
        secret = self._settings.turnstile_secret or self._settings.hcaptcha_secret
        await verify_turnstile(
            secret=secret,
            token=captcha_token,
            remoteip=remoteip,
            disabled=self._settings.backend_captcha_disabled,
        )
        if remoteip:
            await self._codes.check_rate_limit(remoteip)

        code = await self._codes.issue(email)
        subject, html, text = build_code_email(code)
        await self._resend.send(to=email, subject=subject, html=html, text=text)

    async def verify_code(self, *, email: str, code: str) -> TokenPair:
        await self._codes.verify(email, code)

        user = await self._users.get_by_email(email)
        if user is None:
            user = await self._users.create(
                email=email, password_hash=None, role=UserRole.TRADER
            )
        if not user.is_active:
            from src.services.auth_service import AuthError

            raise AuthError("user is disabled")

        await self._users.touch_last_login(user)
        return self._auth._issue_tokens(user)  # noqa: SLF001 — единый источник tokens
