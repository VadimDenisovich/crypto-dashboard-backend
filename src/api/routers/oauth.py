"""OAuth router: Google, Yandex, GitHub (стандартный OAuth2) + Telegram (Login Widget).

GET  /api/auth/{provider}/start          → 302 на провайдера
GET  /api/auth/{provider}/callback       → обмен code → token → userinfo →
                                          resolve user → 302 на frontend?access&refresh
GET  /api/auth/telegram/widget-config    → отдаёт username бота
POST /api/auth/telegram/verify           → проверяет HMAC, выдаёт TokenOut
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Path, Request, status
from fastapi.responses import RedirectResponse

from src.api.deps import DbSession, SettingsDep, get_redis
from src.api.schemas.auth import TokenOut
from src.api.schemas.oauth import TelegramLoginIn, TelegramWidgetConfigOut
from src.infrastructure.oauth_clients import (
    OAuthError,
    build_authorize_url,
    consume_state,
    exchange_code_for_token,
    fetch_userinfo,
    get_provider_config,
    issue_state,
)
from src.infrastructure.telegram_auth import TelegramAuthError, verify_telegram_login
from src.repositories.oauth_identity_repo import OAuthIdentityRepository
from src.repositories.user_repo import UserRepository
from src.services.auth_service import AuthService
from src.services.identity_service import IdentityService

router = APIRouter(prefix="/api/auth", tags=["oauth"])

OAUTH_PROVIDERS = {"google", "yandex", "github"}


def _frontend_callback_url(settings, *, access: str, refresh: str) -> str:
    base = settings.backend_frontend_url.rstrip("/")
    qs = urlencode({"access": access, "refresh": refresh})
    return f"{base}/auth/callback?{qs}"


@router.get("/{provider}/start")
async def oauth_start(
    request: Request,
    settings: SettingsDep,
    provider: str = Path(..., pattern="^(google|yandex|github)$"),
) -> RedirectResponse:
    cfg = get_provider_config(settings, provider)
    if not cfg.client_id or not cfg.redirect_uri:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"OAuth provider '{provider}' is not configured",
        )
    state = await issue_state(get_redis(request), provider=provider)
    url = build_authorize_url(cfg, state=state)
    return RedirectResponse(url, status_code=302)


@router.get("/{provider}/callback")
async def oauth_callback(
    request: Request,
    db: DbSession,
    settings: SettingsDep,
    provider: str = Path(..., pattern="^(google|yandex|github)$"),
) -> RedirectResponse:
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    if error:
        return RedirectResponse(
            f"{settings.backend_frontend_url.rstrip('/')}/login?error={error}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing code or state")

    matched_provider = await consume_state(get_redis(request), state=state)
    if matched_provider != provider:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired state")

    cfg = get_provider_config(settings, provider)
    try:
        token = await exchange_code_for_token(cfg, code=code)
        access = token.get("access_token")
        if not access:
            raise OAuthError("no access_token in response")
        userinfo = await fetch_userinfo(cfg, access_token=access)
    except OAuthError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"oauth: {exc}") from exc
    except Exception as exc:  # httpx errors
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"oauth provider error: {exc}") from exc

    identities = OAuthIdentityRepository(db)
    users = UserRepository(db)
    identity_service = IdentityService(users, identities)
    user = await identity_service.resolve_or_create(
        provider=provider, subject=userinfo.subject, email=userinfo.email
    )

    auth = AuthService(users, settings)
    pair = auth.issue_tokens(user)
    return RedirectResponse(
        _frontend_callback_url(
            settings, access=pair.access_token, refresh=pair.refresh_token
        ),
        status_code=302,
    )


@router.get("/telegram/widget-config", response_model=TelegramWidgetConfigOut)
async def telegram_widget_config(settings: SettingsDep) -> TelegramWidgetConfigOut:
    if not settings.telegram_bot_username:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "TELEGRAM_BOT_USERNAME not configured",
        )
    if not settings.telegram_bot_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "TELEGRAM_BOT_TOKEN not configured",
        )
    # bot_id — numeric prefix перед ':' в токене (Telegram.Login.auth требует именно его)
    try:
        bot_id = int(settings.telegram_bot_token.strip().split(":", 1)[0])
    except (ValueError, IndexError) as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "TELEGRAM_BOT_TOKEN malformed (expected <id>:<token>)",
        ) from exc
    return TelegramWidgetConfigOut(
        bot_id=bot_id,
        bot_username=settings.telegram_bot_username,
    )


@router.post("/telegram/verify", response_model=TokenOut)
async def telegram_verify(
    body: TelegramLoginIn, db: DbSession, settings: SettingsDep
) -> TokenOut:
    payload = body.model_dump(exclude_none=True)
    try:
        tg_id = verify_telegram_login(
            payload,
            bot_token=settings.telegram_bot_token,
            max_age_sec=settings.backend_telegram_auth_max_age_sec,
        )
    except TelegramAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    identities = OAuthIdentityRepository(db)
    users = UserRepository(db)
    identity_service = IdentityService(users, identities)
    user = await identity_service.resolve_or_create(
        provider="telegram", subject=str(tg_id), email=None
    )
    auth = AuthService(users, settings)
    pair = auth.issue_tokens(user)
    return TokenOut(access_token=pair.access_token, refresh_token=pair.refresh_token)
