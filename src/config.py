from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    backend_database_url: str = Field(
        default="postgresql+asyncpg://user:postgres@postgres:5432/crypto-db"
    )
    backend_redis_url: str = Field(default="redis://redis:6379/0")

    backend_jwt_secret: str = Field(default="dev-jwt-secret-change-me")
    backend_jwt_algorithm: str = Field(default="HS256")
    backend_access_token_ttl_min: int = Field(default=15)
    backend_refresh_token_ttl_days: int = Field(default=7)

    backend_encryption_key: str = Field(
        default="oABjyJTzjDOLVdZfv5z8XXs5-cdCqoiiaJHZEVJAICE="
    )

    backend_cors_origins: str = Field(default="http://localhost:5173")
    backend_log_level: str = Field(default="INFO")

    backend_pubsub_reconnect_max_seconds: int = Field(default=30)
    backend_ws_send_timeout_seconds: float = Field(default=2.0)
    backend_ws_max_queue: int = Field(default=100)

    # === Phase 2: identity providers (email-code + OAuth) ===
    # Адрес фронта — сюда бэк делает 302 после OAuth callback с JWT в query string.
    backend_frontend_url: str = Field(default="http://localhost:5173")

    # === Dev mode: отключает captcha/email/OAuth ===
    # BACKEND_DEV_MODE=true пропускает капчу, генерит код "000000" для любого email
    # и не отправляет письмо через Resend. Для локальной разработки без внешних сервисов.
    backend_dev_mode: bool = Field(default=False)

    # Cloudflare Turnstile. В dev/CI можно отключить — поставить true.
    backend_captcha_disabled: bool = Field(default=False)
    turnstile_secret: str = Field(default="")
    # Алиас для обратной совместимости со старой Phase 2 переменной.
    # Если задана hcaptcha_secret и не задана turnstile_secret — используем её.
    hcaptcha_secret: str = Field(default="")

    # Resend (отправка email с кодом).
    resend_api_key: str = Field(default="")
    resend_sender_email: str = Field(default="")
    resend_sender_name: str = Field(default="Crypto Dashboard")
    backend_email_code_ttl_sec: int = Field(default=600)
    backend_email_code_max_attempts: int = Field(default=5)
    backend_email_request_rate_limit_per_min: int = Field(default=3)

    # OAuth: Google, Yandex, GitHub.
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(default="")

    yandex_client_id: str = Field(default="")
    yandex_client_secret: str = Field(default="")
    yandex_redirect_uri: str = Field(default="")

    gh_client_id: str = Field(default="")
    gh_client_secret: str = Field(default="")
    gh_redirect_uri: str = Field(default="")

    # Telegram (Login Widget).
    telegram_bot_token: str = Field(default="")
    telegram_bot_username: str = Field(default="")
    backend_telegram_auth_max_age_sec: int = Field(default=86400)

    # === Phase 4: Backtest engine ===
    # Команда запуска backtest CLI движка (subprocess из backend контейнера).
    # На проде в backend-образе движок ставится через pip install -e /opt/engine[backtest],
    # поэтому "python -m backtest_main" доступен из PATH.
    backend_backtest_cmd: str = Field(default="python -m backtest_main")
    # Папка с parquet-файлами исторических свечей.
    backend_historical_dir: str = Field(default="/data/historical")
    # Максимальное время одного backtest-прогона (через subprocess timeout).
    backend_backtest_timeout_sec: int = Field(default=1800)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
