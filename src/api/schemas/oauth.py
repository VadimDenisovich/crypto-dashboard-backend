from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramLoginIn(BaseModel):
    """Payload, который Telegram Login Widget передаёт в `data-onauth` callback."""

    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str = Field(min_length=1)


class TelegramWidgetConfigOut(BaseModel):
    # bot_id — numeric, нужен для programmatic Telegram.Login.auth({bot_id, ...}).
    # bot_username — для отображения / data-telegram-login script-варианта виджета.
    bot_id: int
    bot_username: str
