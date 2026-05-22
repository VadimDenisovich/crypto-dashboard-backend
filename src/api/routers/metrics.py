from __future__ import annotations

from time import perf_counter
from typing import Awaitable, Callable

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response as StarletteResponse

router = APIRouter(tags=["metrics"])

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the backend.",
    ("method", "endpoint", "http_status"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("endpoint",),
)

CallNext = Callable[[Request], Awaitable[StarletteResponse]]


def _endpoint_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str):
        return route_path
    return request.url.path


async def prometheus_middleware(
    request: Request, call_next: CallNext
) -> StarletteResponse:
    if request.url.path == "/metrics":
        return await call_next(request)

    start = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        endpoint = _endpoint_label(request)
        elapsed = perf_counter() - start
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=endpoint,
            http_status=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(elapsed)


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
