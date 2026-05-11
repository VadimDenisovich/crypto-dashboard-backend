from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OrderOut(BaseModel):
    id: uuid.UUID
    bot_id: uuid.UUID | None
    exchange_order_id: str
    symbol: str
    side: str
    type: str
    size: Decimal
    price: Decimal | None
    status: str
    strategy: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TradeOut(BaseModel):
    id: uuid.UUID
    bot_id: uuid.UUID | None
    symbol: str
    side: str
    size: Decimal
    price: Decimal
    fee: Decimal
    strategy: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    credential_id: uuid.UUID
    currency: str
    free: Decimal
    used: Decimal
    total: Decimal
    observed_at: datetime

    model_config = {"from_attributes": True}
