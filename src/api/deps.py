from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.infrastructure import security
from src.infrastructure.command_publisher import CommandPublisher
from src.infrastructure.crypto import Cipher
from src.infrastructure.ws_manager import ConnectionManager
from src.models.user import User
from src.repositories.user_repo import UserRepository


bearer_scheme = HTTPBearer(auto_error=True)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_cipher(request: Request) -> Cipher:
    return request.app.state.cipher  # type: ignore[no-any-return]


def get_publisher(request: Request) -> CommandPublisher:
    return request.app.state.publisher  # type: ignore[no-any-return]


def get_ws_manager(request: Request) -> ConnectionManager:
    return request.app.state.ws_manager  # type: ignore[no-any-return]


def get_redis(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.redis


def get_resend(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.resend


def get_email_codes(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.email_codes


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
CipherDep = Annotated[Cipher, Depends(get_cipher)]
PublisherDep = Annotated[CommandPublisher, Depends(get_publisher)]
WsManagerDep = Annotated[ConnectionManager, Depends(get_ws_manager)]


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: DbSession,
    settings: SettingsDep,
) -> User:
    try:
        payload = security.decode_token(
            creds.credentials, settings.backend_jwt_secret, settings.backend_jwt_algorithm
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    user = await UserRepository(db).get_by_id(uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
