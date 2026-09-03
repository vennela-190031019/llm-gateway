"""Application entrypoint.

Wires together configuration, structured logging, CORS, and API routers.
Business logic never lives here — this module only assembles the app.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse, Response

from app.api.v1 import auth, chat, evaluations, health, models, prompts, requests
from app.api.v1 import metrics as metrics_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    REQUEST_ID_HEADER,
    REQUEST_ID_STATE_KEY,
    TRACE_ID_HEADER,
    TRACE_ID_STATE_KEY,
    HTTPMetricsMiddleware,
    MaxBodySizeMiddleware,
    RequestTracingMiddleware,
)
from app.core.rate_limit import limiter

settings = get_settings()
configure_logging(log_level=settings.log_level, json_logs=settings.is_production)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("app_starting", env=settings.app_env)
    yield
    logger.info("app_stopping")


app = FastAPI(
    title=settings.app_name,
    description="Production-grade LLM Gateway & Observability Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Same `{"detail": ...}` shape as every other error response in this
    API — slowapi's own default handler uses `{"error": ...}`, which
    would be an inconsistent one-off.
    """
    return JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches anything not already handled by a more specific handler —
    FastAPI's own handlers for HTTPException/RequestValidationError (and
    ours for RateLimitExceeded above) still win, since Starlette's
    handler lookup matches the most specific registered exception type
    first. This is only the fallback for genuinely unexpected errors.

    Logs full details server-side, including a formatted traceback, but
    returns a generic message to the client — no exception type,
    message, or traceback, any of which could hand an attacker
    information about internals worth probing further.

    A handler for the base Exception type is special-cased by Starlette:
    it runs inside `ServerErrorMiddleware`, which — unlike every other
    exception handler — sits *outside* every middleware registered via
    `app.add_middleware()`, including RequestTracingMiddleware. So this
    response never passes through that middleware's own header
    injection, and by the time we get here its contextvars have already
    been unbound (normal stack-unwind order). Both ids are still
    reachable via `request.state` though — see that middleware's
    docstring — so we attach them here explicitly instead.
    """
    request_id = getattr(request.state, REQUEST_ID_STATE_KEY, None)
    trace_id = getattr(request.state, TRACE_ID_STATE_KEY, None)

    logger.error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error_type=type(exc).__name__,
        request_id=request_id,
        trace_id=trace_id,
        exc_info=exc,
    )
    response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    if request_id is not None:
        response.headers[REQUEST_ID_HEADER] = request_id
    if trace_id is not None:
        response.headers[TRACE_ID_HEADER] = trace_id
    return response


# Rate limiting isn't ASGI middleware here — see app.core.rate_limit's
# module docstring for why every route carries an explicit
# @limiter.limit(...) decorator instead. Middleware added later wraps
# outside what's added earlier, so tracing (which every log line and the
# metrics middleware itself can benefit from) ends up outermost, running
# before — and completing after — HTTP-metrics timing. Body-size
# limiting is outermost of all — no point tracing/counting a request
# we're about to reject purely for being too large, and it must run
# before anything else tries to buffer the body.
app.add_middleware(HTTPMetricsMiddleware)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)

API_PREFIX = "/api/v1"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(models.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(requests.router, prefix=API_PREFIX)
app.include_router(prompts.router, prefix=API_PREFIX)
app.include_router(evaluations.router, prefix=API_PREFIX)
app.include_router(metrics_router.router, prefix=API_PREFIX)


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint (kept at root, not under /api/v1)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
