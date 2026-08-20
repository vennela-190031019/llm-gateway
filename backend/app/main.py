"""Application entrypoint.

Wires together configuration, structured logging, CORS, and API routers.
Business logic never lives here — this module only assembles the app.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.v1 import auth, chat, evaluations, health, models, prompts, requests
from app.api.v1 import metrics as metrics_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

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
