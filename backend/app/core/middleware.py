"""Request-tracing and HTTP-metrics ASGI middleware.

`RequestTracingMiddleware` assigns (or honors) a request_id/trace_id per
request, binds them to structlog's contextvars so every log line emitted
while handling the request automatically includes them, and echoes them
back as response headers so callers/logs on both sides can correlate.

`HTTPMetricsMiddleware` records the two HTTP-level Prometheus metrics
(http_requests_total, http_request_duration_seconds) — kept separate
from the LLM-specific metrics in app.core.metrics, which only cover
requests that actually call an LLM provider.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import http_request_duration_seconds, http_requests_total

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"

_Endpoint = Callable[[Request], Awaitable[Response]]


class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: _Endpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        trace_id = request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())

        structlog.contextvars.bind_contextvars(request_id=request_id, trace_id=trace_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "trace_id")

        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        return response


def _route_template(request: Request) -> str:
    """The request path with any matched path parameters replaced by their
    placeholder name (e.g. "/api/v1/prompts/{name}/render"), so the `path`
    label's cardinality stays bounded regardless of how many distinct
    resource names/ids are requested.

    Deliberately doesn't use `request.scope["route"].path`: FastAPI
    resolves `include_router`-mounted routers through an internal
    wrapper, so the matched route only knows its own local path template
    ("/healthz"), not the full mounted one ("/api/v1/healthz").
    `request.path_params` is populated by the same routing step and
    reflects the fully-resolved request, so substituting from it back
    into the literal URL reconstructs the full template without
    depending on that internal structure. Requests that never matched a
    route (404s) have no path params, so this is a no-op and the raw
    path is used as-is.
    """
    path = request.url.path
    for key, value in request.path_params.items():
        token = str(value)
        if token:
            path = path.replace(token, "{" + key + "}")
    return path


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: _Endpoint) -> Response:
        started = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_seconds = time.monotonic() - started
            path = _route_template(request)
            http_requests_total.labels(
                method=request.method, path=path, status_code=str(status_code)
            ).inc()
            http_request_duration_seconds.labels(method=request.method, path=path).observe(
                duration_seconds
            )
