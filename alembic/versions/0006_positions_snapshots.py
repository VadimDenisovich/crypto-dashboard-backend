"""add positions_snapshots table

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-21

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "positions_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("credential_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("exchange_credentials.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("entry_price", sa.Numeric(36, 18), nullable=False),
        sa.Column("size", sa.Numeric(36, 18), nullable=False),
        sa.Column("current_pnl", sa.Numeric(36, 18), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("positions_snapshots")
