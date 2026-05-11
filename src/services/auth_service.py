from __future__ import annotations

from dataclasses import dataclass

from src.config import Settings
from src.infrastructure import security
from src.models.user import User, UserRole
from src.repositories.user_repo import UserRepository


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    async def register(self, *, email: str, password: str) -> User:
        if await self._users.get_by_email(email):
            raise AuthError("email already registered")
        return await self._users.create(
            email=email,
            password_hash=security.hash_password(password),
            role=UserRole.TRADER,
        )

    async def login(self, *, email: str, password: str) -> TokenPair:
        user = await self._users.get_by_email(email)
        if not user or not user.is_active:
            raise AuthError("invalid credentials")
        if not security.verify_password(password, user.password_hash):
            raise AuthError("invalid credentials")
        return self._issue_tokens(user)

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        try:
            payload = security.decode_token(
                refresh_token,
                self._settings.backend_jwt_secret,
                self._settings.backend_jwt_algorithm,
            )
        except ValueError as exc:
            raise AuthError("invalid refresh token") from exc
        if payload.get("type") != "refresh":
            raise AuthError("invalid token type")
        import uuid as _uuid
        user = await self._users.get_by_id(_uuid.UUID(payload["sub"]))
        if not user or not user.is_active:
            raise AuthError("user not found")
        return self._issue_tokens(user)

    def _issue_tokens(self, user: User) -> TokenPair:
        access = security.encode_access_token(
            user_id=user.id,
            role=user.role.value,
            secret=self._settings.backend_jwt_secret,
            algorithm=self._settings.backend_jwt_algorithm,
            ttl_minutes=self._settings.backend_access_token_ttl_min,
        )
        refresh = security.encode_refresh_token(
            user_id=user.id,
            secret=self._settings.backend_jwt_secret,
            algorithm=self._settings.backend_jwt_algorithm,
            ttl_days=self._settings.backend_refresh_token_ttl_days,
        )
        return TokenPair(access_token=access, refresh_token=refresh)
