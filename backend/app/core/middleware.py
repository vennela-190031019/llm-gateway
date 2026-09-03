"""Request-tracing, HTTP-metrics, and body-size-limiting ASGI middleware.

`RequestTracingMiddleware` assigns (or honors) a request_id/trace_id per
request, binds them to structlog's contextvars so every log line emitted
while handling the request automatically includes them, and echoes them
back as response headers so callers/logs on both sides can correlate.
It also stashes both ids in `request.state` (see REQUEST_STATE_KEY),
which matters specifically for app.main's global exception handler: for
a *truly* unhandled exception, Starlette's always-present
`ServerErrorMiddleware` is what actually produces the response, and it
sits outside every middleware registered via `app.add_middleware()` —
including this one. By the time an exception reaches it, this
middleware's own `finally` has already unbound the contextvars (normal
stack-unwind order), so the handler can't rely on them; reading back
from `request.state` — a plain dict on the ASGI scope, unaffected by
contextvar lifecycle — lets it recover the same ids anyway, for both the
log line and the response headers, which otherwise wouldn't get to run
through `send_with_trace_headers` at all in that one path.

`HTTPMetricsMiddleware` records the two HTTP-level Prometheus metrics
(http_requests_total, http_request_duration_seconds) — kept separate
from the LLM-specific metrics in app.core.metrics, which only cover
requests that actually call an LLM provider.

`MaxBodySizeMiddleware` rejects oversized request bodies (413) before
they're ever buffered into memory — see its own docstring.

All three are plain ASGI middleware (a `__call__(scope, receive, send)`),
not `starlette.middleware.base.BaseHTTPMiddleware`, deliberately: when an
unhandled exception reaches app.main's global exception handler,
Starlette's exception middleware handles it and sends a response, but
*also* re-raises the original exception afterward so outer layers can
observe it too. `BaseHTTPMiddleware.call_next()` reacts to that re-raise
by raising again itself — and with several `BaseHTTPMiddleware`s
stacked, that cascades into a second, conflicting attempt to send a
response (an ASGI protocol violation: httpx's ASGITransport surfaces it
as a broken request; real ASGI servers vary in how gracefully they
absorb it). Plain ASGI middleware just lets the exception propagate
naturally through a `finally` block instead, which doesn't have this
failure mode — see https://github.com/encode/starlette/discussions/1527.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.metrics import http_request_duration_seconds, http_requests_total

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"

# Keys under request.state — see the module docstring for why this
# exists alongside the contextvars binding below.
REQUEST_ID_STATE_KEY = "request_id"
TRACE_ID_STATE_KEY = "trace_id"


class RequestTracingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        trace_id = headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())

        state = scope.setdefault("state", {})
        state[REQUEST_ID_STATE_KEY] = request_id
        state[TRACE_ID_STATE_KEY] = trace_id

        async def send_with_trace_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(raw=message["headers"])
                response_headers.append(REQUEST_ID_HEADER, request_id)
                response_headers.append(TRACE_ID_HEADER, trace_id)
            await send(message)

        structlog.contextvars.bind_contextvars(request_id=request_id, trace_id=trace_id)
        try:
            await self.app(scope, receive, send_with_trace_headers)
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "trace_id")


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


class HTTPMetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        status_code = 500

        async def send_and_capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        request = Request(scope)
        try:
            await self.app(scope, receive, send_and_capture_status)
        finally:
            duration_seconds = time.monotonic() - started
            path = _route_template(request)
            http_requests_total.labels(
                method=request.method, path=path, status_code=str(status_code)
            ).inc()
            http_request_duration_seconds.labels(method=request.method, path=path).observe(
                duration_seconds
            )


class _RequestBodyTooLarge(Exception):
    """Internal signal only — never escapes this module."""


class MaxBodySizeMiddleware:
    """Rejects request bodies larger than `max_bytes` with a 413.

    Checks the declared Content-Length up front — the common case, since
    every JSON client sets it, and it lets us reject before reading a
    single byte of an honestly-labeled oversized body — and also
    enforces the same limit against actual bytes received as they
    stream in, so a request that omits Content-Length (or understates
    it, e.g. chunked transfer encoding) can't slip a huge body past the
    header check.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None and content_length.isdigit():
            if int(content_length) > self.max_bytes:
                await self._reject(scope, receive, send)
                return

        received = 0

        async def guarded_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body") or b"")
            if received > self.max_bytes:
                raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, guarded_receive, send)
        except _RequestBodyTooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": f"Request body too large (max {self.max_bytes} bytes)."},
        )
        await response(scope, receive, send)
