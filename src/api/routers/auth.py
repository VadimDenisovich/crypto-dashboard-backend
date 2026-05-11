from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CurrentUser, DbSession, SettingsDep
from src.api.schemas.auth import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from src.repositories.user_repo import UserRepository
from src.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, db: DbSession, settings: SettingsDep) -> UserOut:
    service = AuthService(UserRepository(db), settings)
    try:
        user = await service.register(email=body.email, password=body.password)
    except AuthError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: DbSession, settings: SettingsDep) -> TokenOut:
    service = AuthService(UserRepository(db), settings)
    try:
        pair = await service.login(email=body.email, password=body.password)
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
