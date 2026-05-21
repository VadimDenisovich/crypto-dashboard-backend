from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CommandKind(str, enum.Enum):
    START = "start"
    STOP = "stop"
    UPDATE = "update"


class BotCommand(Base, TimestampMixin):
    __tablename__ = "bot_commands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    command_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[CommandKind] = mapped_column(
        SAEnum(
            CommandKind,
            name="command_kind",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
