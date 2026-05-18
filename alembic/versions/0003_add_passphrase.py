"""add passphrase_enc to exchange_credentials

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-19

Phase 3 (Multi-exchange): OKX и Coinbase Pro требуют третий секрет — passphrase.
Колонка nullable, Binance/Bybit/MEXC её не используют.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exchange_credentials",
        sa.Column("passphrase_enc", sa.String, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exchange_credentials", "passphrase_enc")
