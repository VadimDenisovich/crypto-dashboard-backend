"""oauth identities + drop existing users

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14

Phase 2 (Auth IdP): убираем password-логин, переходим на OAuth + email-code.
- Делаем `users.password_hash` nullable (старая колонка остаётся, но не используется).
- Добавляем `users.updated_at` и `users.last_login_at`.
- Создаём таблицу `oauth_identities` с UNIQUE (provider, subject).
- TRUNCATE всех данных: пользователи пересоздаются через UI.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Сносим все данные. CASCADE цепляет bots, exchange_credentials, orders,
    #    trades, balance_snapshots, strategy_errors, bot_commands.
    op.execute("TRUNCATE TABLE users CASCADE")

    # 2. password_hash больше не обязателен.
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)

    # 3. Новые служебные колонки.
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 4. Привязки OAuth-провайдеров к пользователю.
    op.create_table(
        "oauth_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("provider", "subject", name="uq_oauth_identities_provider_subject"),
    )
    op.create_index(
        "ix_oauth_identities_user", "oauth_identities", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_identities_user", table_name="oauth_identities")
    op.drop_table("oauth_identities")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "updated_at")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
