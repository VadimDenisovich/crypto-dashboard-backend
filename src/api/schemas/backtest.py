from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BacktestRunIn(BaseModel):
    strategy_class: str = Field(..., min_length=1, max_length=64)
    symbol: str = Field(..., min_length=3, max_length=32)
    timeframe: str = Field(..., min_length=1, max_length=8)
    params: dict[str, Any] = Field(default_factory=dict)
    date_from: datetime
    date_to: datetime
    initial_balance: dict[str, str] = Field(
        default_factory=lambda: {"USDT": "10000"},
        description="Currency → amount (string for Decimal precision)",
    )


class BacktestJobOut(BaseModel):
    id: uuid.UUID
    status: str
    strategy_class: str
    symbol: str
    timeframe: str
    params: dict[str, Any]
    date_from: datetime
    date_to: datetime
    initial_balance: dict[str, str]
    result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class BacktestJobSummaryOut(BaseModel):
    """Облегчённое представление для списка — без `result.trades` и `equity_curve`."""

    id: uuid.UUID
    status: str
    strategy_class: str
    symbol: str
    timeframe: str
    created_at: datetime
    completed_at: datetime | None
    total_return_pct: str | None = None
    trades_count: int | None = None

    model_config = {"from_attributes": True}
