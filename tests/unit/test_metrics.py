from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.routers.metrics import prometheus_middleware, router


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_http_metrics() -> None:
    app = FastAPI()
    app.middleware("http")(prometheus_middleware)

    @app.get("/items/{item_id}")
    async def read_item(item_id: str) -> dict[str, Any]:
        return {"item_id": item_id}

    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/items/123")
        assert response.status_code == 200

        metrics_response = await client.get("/metrics")

    assert metrics_response.status_code == 200
    body = metrics_response.text
    assert (
        'http_requests_total{endpoint="/items/{item_id}",'
        'http_status="200",method="GET"}'
    ) in body
    assert 'http_request_duration_seconds_bucket{endpoint="/items/{item_id}"' in body
    assert 'endpoint="/metrics"' not in body
