"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-11

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role = postgresql.ENUM(
    "admin", "trader", "viewer", name="user_role", create_type=False
)
bot_status = postgresql.ENUM(
    "draft",
    "starting",
    "running",
    "stopping",
    "stopped",
    "error",
    name="bot_status",
    create_type=False,
)
command_kind = postgresql.ENUM(
    "start", "stop", "update", name="command_kind", create_type=False
)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    bot_status.create(op.get_bind(), checkfirst=True)
    command_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="trader"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "exchange_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("api_key_enc", sa.String, nullable=False),
        sa.Column("api_secret_enc", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_exchange_credentials_user_id", "exchange_credentials", ["user_id"]
    )

    op.create_table(
        "bots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exchange_credentials.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("strategy_class", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", bot_status, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bots_user_id", "bots", ["user_id"])

    op.create_table(
        "bot_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column(
            "bot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", command_kind, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bot_commands_bot_id", "bot_commands", ["bot_id"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("exchange_order_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("size", sa.Numeric(36, 18), nullable=False),
        sa.Column("price", sa.Numeric(36, 18), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("exchange_order_id", "bot_id", name="uq_order_exchange_bot"),
    )
    op.create_index("ix_orders_bot_id", "orders", ["bot_id"])
    op.create_index("ix_orders_exchange_order_id", "orders", ["exchange_order_id"])

    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("size", sa.Numeric(36, 18), nullable=False),
        sa.Column("price", sa.Numeric(36, 18), nullable=False),
        sa.Column("fee", sa.Numeric(36, 18), nullable=False, server_default="0"),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trades_bot_id", "trades", ["bot_id"])

    op.create_table(
        "balances_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "credential_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exchange_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("free", sa.Numeric(36, 18), nullable=False),
        sa.Column("used", sa.Numeric(36, 18), nullable=False),
        sa.Column("total", sa.Numeric(36, 18), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_balances_credential_id", "balances_snapshots", ["credential_id"])
    op.create_index("ix_balances_observed_at", "balances_snapshots", ["observed_at"])

    op.create_table(
        "strategy_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("strategy", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("raw", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_strategy_errors_bot_id", "strategy_errors", ["bot_id"])


def downgrade() -> None:
    op.drop_index("ix_strategy_errors_bot_id", table_name="strategy_errors")
    op.drop_table("strategy_errors")
    op.drop_index("ix_balances_observed_at", table_name="balances_snapshots")
    op.drop_index("ix_balances_credential_id", table_name="balances_snapshots")
    op.drop_table("balances_snapshots")
    op.drop_index("ix_trades_bot_id", table_name="trades")
    op.drop_table("trades")
    op.drop_index("ix_orders_exchange_order_id", table_name="orders")
    op.drop_index("ix_orders_bot_id", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_bot_commands_bot_id", table_name="bot_commands")
    op.drop_table("bot_commands")
    op.drop_index("ix_bots_user_id", table_name="bots")
    op.drop_table("bots")
    op.drop_index("ix_exchange_credentials_user_id", table_name="exchange_credentials")
    op.drop_table("exchange_credentials")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    command_kind.drop(op.get_bind(), checkfirst=True)
    bot_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
