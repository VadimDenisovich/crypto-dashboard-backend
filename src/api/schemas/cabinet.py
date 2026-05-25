from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreateIn(BaseModel):
    label: str | None = Field(default=None, max_length=64)


class ApiKeyOut(BaseModel):
    """Список ключей — без полного секрета, только префикс для отображения."""

    id: uuid.UUID
    label: str
    key_prefix: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateOut(ApiKeyOut):
    """Ответ на создание — содержит полный ключ, показывается ровно один раз."""

    key: str


class TwoFaStateOut(BaseModel):
    enabled: bool


class TwoFaSetupOut(BaseModel):
    otpauth_uri: str


class TwoFaVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TestConnectionOut(BaseModel):
    message: str
