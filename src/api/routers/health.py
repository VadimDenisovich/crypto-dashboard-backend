from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    checks: dict[str, str] = {"backend": "ok"}
    code = status.HTTP_200_OK

    try:
        engine = request.app.state.db_engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc!s}"
        code = status.HTTP_503_SERVICE_UNAVAILABLE

    try:
        redis = request.app.state.redis
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc!s}"
        code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(checks, status_code=code)
