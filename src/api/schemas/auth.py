from __future__ import annotations

import uuid

from pydantic import BaseModel


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    # str (а не EmailStr) — Telegram-юзеры имеют synthetic email с зарезервированным
    # TLD (см. identity_service._synth_email), который не проходит EmailStr.
    # На вход email мы всё ещё валидируем через EmailStr (см. email_auth.py).
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
