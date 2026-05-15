from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
