from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class UserApiKey(Base, TimestampMixin):
    """API ключ для программного доступа клиента к нашему /api/external/*.

    Полный секрет (формата `cd_<32hex>`) клиент видит ровно один раз — при
    создании. В БД храним только bcrypt-хеш + первые 12 символов (key_prefix)
    для быстрого поиска при верификации входящего запроса.
    """

    __tablename__ = "user_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
