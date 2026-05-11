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
        default="ZmRldi1mZXJuZXQta2V5LXBsZWFzZS1jaGFuZ2UtaW4tcHJvZD0="
    )

    backend_cors_origins: str = Field(default="http://localhost:5173")
    backend_log_level: str = Field(default="INFO")

    backend_pubsub_reconnect_max_seconds: int = Field(default=30)
    backend_ws_send_timeout_seconds: float = Field(default=2.0)
    backend_ws_max_queue: int = Field(default=100)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
