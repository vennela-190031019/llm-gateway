"""Isolated unit tests for app.core.middleware — built against a minimal
FastAPI app (not app.main) so these stay focused on the middleware
itself, with no DB/auth/provider setup involved.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.logging import get_logger
from app.core.middleware import REQUEST_ID_HEADER, TRACE_ID_HEADER, RequestTracingMiddleware

logger = get_logger(__name__)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestTracingMiddleware)

    @app.get("/probe")
    async def probe() -> dict[str, str]:
        logger.info("probe_hit")
        return {"status": "ok"}

    return app


@pytest.fixture
async def probe_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_generates_request_id_and_trace_id_when_absent(
    probe_client: AsyncClient,
) -> None:
    response = await probe_client.get("/probe")

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]
    assert response.headers[TRACE_ID_HEADER]
    # They should be valid, distinct UUIDs, not e.g. the same value reused.
    assert response.headers[REQUEST_ID_HEADER] != response.headers[TRACE_ID_HEADER]


async def test_honors_request_id_and_trace_id_provided_via_headers(
    probe_client: AsyncClient,
) -> None:
    response = await probe_client.get(
        "/probe",
        headers={REQUEST_ID_HEADER: "given-request-id", TRACE_ID_HEADER: "given-trace-id"},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "given-request-id"
    assert response.headers[TRACE_ID_HEADER] == "given-trace-id"


async def test_different_requests_get_different_ids(probe_client: AsyncClient) -> None:
    first = await probe_client.get("/probe")
    second = await probe_client.get("/probe")

    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]


async def test_request_id_and_trace_id_appear_in_logs(probe_client: AsyncClient) -> None:
    with structlog.testing.capture_logs(
        processors=[structlog.contextvars.merge_contextvars]
    ) as captured:
        response = await probe_client.get("/probe")

    probe_logs = [entry for entry in captured if entry.get("event") == "probe_hit"]
    assert len(probe_logs) == 1
    assert probe_logs[0]["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert probe_logs[0]["trace_id"] == response.headers[TRACE_ID_HEADER]


async def test_contextvars_are_unbound_after_request(probe_client: AsyncClient) -> None:
    await probe_client.get("/probe", headers={REQUEST_ID_HEADER: "leaky-check"})

    # A second, unrelated request must not inherit the previous request's id.
    with structlog.testing.capture_logs(
        processors=[structlog.contextvars.merge_contextvars]
    ) as captured:
        await probe_client.get("/probe")

    probe_logs = [entry for entry in captured if entry.get("event") == "probe_hit"]
    assert probe_logs[0]["request_id"] != "leaky-check"
