from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, utcnow


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    # Стало nullable после Phase 2: password-логин убран, OAuth/email-code пользователи
    # создаются без пароля. Поле сохраняется для миграции старых записей.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        # values_callable: SQLAlchemy будет писать в БД 'trader'/'admin'/'viewer'
        # (значения), а не 'TRADER'/'ADMIN'/'VIEWER' (имена). PG ENUM в миграции 0001
        # объявлен в lowercase — без values_callable INSERT валится с InvalidTextRepresentation.
        SAEnum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_constraint=False,
        ),
        default=UserRole.TRADER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
