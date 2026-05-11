from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CredentialIn(BaseModel):
    exchange: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=1, max_length=512)
    api_secret: str = Field(min_length=1, max_length=512)


class CredentialOut(BaseModel):
    id: uuid.UUID
    exchange: str
    label: str
    created_at: datetime

    model_config = {"from_attributes": True}
