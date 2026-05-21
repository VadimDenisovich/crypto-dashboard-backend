FROM python:3.14-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels .

FROM python:3.14-slim AS runtime

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# gosu - нужен entrypoint-скрипту для сброса привилегий после chown на data/historical
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 curl gosu && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --gid ${APP_GID} app 2>/dev/null || true && \
    useradd --create-home --uid ${APP_UID} --gid ${APP_GID} app

WORKDIR /app
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Phase 4 (backtest): pandas/pyarrow нужны движку при запуске backtest_main
# subprocess'а. Ставим их в backend-образ, чтобы subprocess мог импортировать.
# Сам движок монтируется bind-mount'ом через docker-compose (PYTHONPATH=/opt/engine/src).
RUN pip install --no-cache-dir "pandas>=2.2" "pyarrow>=15"

COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app src ./src

# entrypoint чинит права на /data/historical и сбрасывает root → app
COPY --chown=app:app docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
