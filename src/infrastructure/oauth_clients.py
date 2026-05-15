"""OAuth2 клиенты для Google, Yandex, GitHub.

Authlib AsyncOAuth2Client — обёртка над httpx, делает code → token обмен.
Userinfo дёргается отдельно через httpx (у каждого провайдера свой формат).

Не используем authlib.integrations.starlette_client (он завязан на сессии Starlette,
а у нас state хранится в Redis отдельно — проще явно).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from redis.asyncio import Redis

from src.config import Settings


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    scope: str
    # token_endpoint_auth_method для GitHub нужен 'client_secret_post'
    token_auth_method: str = "client_secret_basic"


@dataclass(frozen=True, slots=True)
class UserInfo:
    subject: str
    email: str | None


class OAuthError(Exception):
    pass


def get_provider_config(settings: Settings, provider: str) -> ProviderConfig:
    if provider == "google":
        return ProviderConfig(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope="openid email profile",
        )
    if provider == "yandex":
        return ProviderConfig(
            name="yandex",
            client_id=settings.yandex_client_id,
            client_secret=settings.yandex_client_secret,
            redirect_uri=settings.yandex_redirect_uri,
            authorize_url="https://oauth.yandex.ru/authorize",
            token_url="https://oauth.yandex.ru/token",
            scope="login:email",
        )
    if provider == "github":
        return ProviderConfig(
            name="github",
            client_id=settings.gh_client_id,
            client_secret=settings.gh_client_secret,
            redirect_uri=settings.gh_redirect_uri,
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scope="read:user user:email",
            token_auth_method="client_secret_post",
        )
    raise OAuthError(f"unknown OAuth provider: {provider}")


# === State (CSRF protection) — хранится в Redis ===

_STATE_KEY = "auth:oauth_state:{state}"
_STATE_TTL_SEC = 600


async def issue_state(redis: Redis, *, provider: str) -> str:
    state = secrets.token_urlsafe(24)
    await redis.set(_STATE_KEY.format(state=state), provider, ex=_STATE_TTL_SEC)
    return state


async def consume_state(redis: Redis, *, state: str) -> str | None:
    """Возвращает provider если state валиден; удаляет ключ (one-shot)."""
    key = _STATE_KEY.format(state=state)
    pipe = redis.pipeline()
    pipe.get(key)
    pipe.delete(key)
    raw, _ = await pipe.execute()
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


# === code → token + userinfo ===


def _build_client(cfg: ProviderConfig) -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        redirect_uri=cfg.redirect_uri,
        scope=cfg.scope,
        token_endpoint_auth_method=cfg.token_auth_method,
    )


def build_authorize_url(cfg: ProviderConfig, *, state: str) -> str:
    extra: dict[str, Any] = {}
    if cfg.name == "google":
        # Чтобы каждый раз получать refresh-token и работала смена аккаунтов.
        extra["access_type"] = "offline"
        extra["prompt"] = "select_account"
    client = _build_client(cfg)
    try:
        url, _ = client.create_authorization_url(cfg.authorize_url, state=state, **extra)
        return str(url)
    finally:
        # AsyncOAuth2Client держит httpx-сессию — закроем её отдельным контекстом
        # при актуальных запросах. Здесь create_authorization_url синхронный.
        pass


async def exchange_code_for_token(cfg: ProviderConfig, *, code: str) -> dict[str, Any]:
    async with _build_client(cfg) as client:
        # GitHub возвращает application/x-www-form-urlencoded по умолчанию,
        # просим JSON через Accept-заголовок.
        headers = {"Accept": "application/json"} if cfg.name == "github" else None
        token = await client.fetch_token(
            cfg.token_url,
            code=code,
            headers=headers,
        )
        return dict(token)


async def fetch_userinfo(cfg: ProviderConfig, *, access_token: str) -> UserInfo:
    headers = {"Authorization": f"Bearer {access_token}"}

    if cfg.name == "google":
        url = "https://openidconnect.googleapis.com/v1/userinfo"
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        return UserInfo(subject=str(data["sub"]), email=data.get("email"))

    if cfg.name == "yandex":
        # Яндекс ждёт `OAuth <token>` (не Bearer).
        url = "https://login.yandex.ru/info?format=json"
        ya_headers = {"Authorization": f"OAuth {access_token}"}
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(url, headers=ya_headers)
        r.raise_for_status()
        data = r.json()
        email = data.get("default_email") or (data.get("emails") or [None])[0]
        return UserInfo(subject=str(data["id"]), email=email)

    if cfg.name == "github":
        async with httpx.AsyncClient(timeout=10.0) as c:
            user_resp = await c.get("https://api.github.com/user", headers=headers)
            user_resp.raise_for_status()
            user_data = user_resp.json()
            email = user_data.get("email")
            if not email:
                # email может быть скрыт; добираем через /user/emails
                em_resp = await c.get("https://api.github.com/user/emails", headers=headers)
                if em_resp.status_code == 200:
                    emails = em_resp.json() or []
                    primary = next(
                        (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                        None,
                    )
                    email = primary
        return UserInfo(subject=str(user_data["id"]), email=email)

    raise OAuthError(f"unknown provider: {cfg.name}")
