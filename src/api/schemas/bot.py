from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BotCreateIn(BaseModel):
    credential_id: uuid.UUID
    strategy_class: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(min_length=1, max_length=8)
    params: dict[str, Any] = Field(default_factory=dict)


class BotParamsIn(BaseModel):
    params: dict[str, Any]


class BotStopIn(BaseModel):
    close_positions: bool = False


class BotOut(BaseModel):
    id: uuid.UUID
    credential_id: uuid.UUID
    strategy_class: str
    symbol: str
    timeframe: str
    params: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
