"""add exchange column to backtest_jobs

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-20

Бэктест теперь привязан к конкретной бирже (раньше всегда binance). Колонка с
server_default='binance' — чтобы существующие записи остались валидными.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "backtest_jobs",
        sa.Column(
            "exchange",
            sa.String(32),
            nullable=False,
            server_default="binance",
        ),
    )


def downgrade() -> None:
    op.drop_column("backtest_jobs", "exchange")
