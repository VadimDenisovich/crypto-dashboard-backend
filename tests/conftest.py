from __future__ import annotations

import os

# Сбрасываем env, чтобы Settings брал дефолты и не падал на отсутствии .env
os.environ.setdefault("BACKEND_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("BACKEND_REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("BACKEND_JWT_SECRET", "test-secret")
os.environ.setdefault(
    "BACKEND_ENCRYPTION_KEY", "ZmRldi1mZXJuZXQta2V5LXBsZWFzZS1jaGFuZ2UtaW4tcHJvZD0="
)
