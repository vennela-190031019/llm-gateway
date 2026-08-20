"""Health check endpoint.

Kept separate from metrics.py (Prometheus scrape target) — this is a
lightweight liveness/readiness probe for load balancers and Docker.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
