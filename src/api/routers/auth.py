"""Auth-роутер: email-code flow + refresh + me.

Phase 2: пароль-логин и регистрация удалены. Регистрация автоматическая
при первом входе через email-code или OAuth.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from src.api.deps import (
    CurrentUser,
    DbSession,
    SettingsDep,
    get_email_codes,
    get_resend,
)
from src.api.schemas.auth import RefreshIn, TokenOut, UserOut
from src.api.schemas.email_auth import EmailRequestIn, EmailRequestOut, EmailVerifyIn
from src.infrastructure.captcha import CaptchaError
from src.infrastructure.email_codes import (
    CodeError,
    CodeLocked,
    CodeMismatch,
    CodeNotFound,
    RateLimited,
)
from src.infrastructure.resend_email import ResendError
from src.repositories.user_repo import UserRepository
from src.services.auth_service import AuthError, AuthService
from src.services.email_auth_service import EmailAuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


@router.post(
    "/email/request",
    response_model=EmailRequestOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def email_request(
    body: EmailRequestIn, request: Request, db: DbSession, settings: SettingsDep
) -> EmailRequestOut:
    service = EmailAuthService(
        settings=settings,
        codes=get_email_codes(request),
        resend=get_resend(request),
        users=UserRepository(db),
        auth=AuthService(UserRepository(db), settings),
    )
    try:
        await service.request_code(
            email=body.email,
            captcha_token=body.captcha_token,
            remoteip=_client_ip(request),
        )
    except CaptchaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RateLimited as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except ResendError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"email send failed: {exc}") from exc
    return EmailRequestOut()


@router.post("/email/verify", response_model=TokenOut)
async def email_verify(
    body: EmailVerifyIn, request: Request, db: DbSession, settings: SettingsDep
) -> TokenOut:
    service = EmailAuthService(
        settings=settings,
        codes=get_email_codes(request),
        resend=get_resend(request),
        users=UserRepository(db),
        auth=AuthService(UserRepository(db), settings),
    )
    try:
        pair = await service.verify_code(email=body.email, code=body.code)
    except CodeNotFound as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except CodeMismatch as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except CodeLocked as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except CodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return TokenOut(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, db: DbSession, settings: SettingsDep) -> TokenOut:
    service = AuthService(UserRepository(db), settings)
    try:
        pair = await service.refresh(refresh_token=body.refresh_token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return TokenOut(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
