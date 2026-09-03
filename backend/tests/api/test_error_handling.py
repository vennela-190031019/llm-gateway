"""Tests for the global exception handler — see
app.main.unhandled_exception_handler.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.repositories import user_repository as user_repository_module


async def test_unhandled_exception_returns_generic_500_without_leaking_details(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forces a genuinely unexpected error (not one of the typed
    exceptions app.api.v1.auth already catches) partway through a real
    request, and confirms the client only ever sees a generic message —
    never the exception type, message, or a traceback.
    """

    async def _boom(self: object, email: str) -> None:
        raise RuntimeError("db exploded: sk-should-not-leak at /etc/secrets/db.conf")

    monkeypatch.setattr(user_repository_module.UserRepository, "get_by_email", _boom)

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "whoever@example.com", "password": "hunter22"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "sk-should-not-leak" not in response.text
    assert "/etc/secrets/db.conf" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
    assert "db_exploded" not in response.text.lower().replace(" ", "_")


async def test_unhandled_exception_response_still_has_request_id_headers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(self: object, email: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(user_repository_module.UserRepository, "get_by_email", _boom)

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "whoever@example.com", "password": "hunter22"},
    )

    assert response.status_code == 500
    assert "x-request-id" in response.headers
    assert "x-trace-id" in response.headers


async def test_normal_errors_are_unaffected_by_the_global_handler(client: AsyncClient) -> None:
    """The catch-all must not shadow FastAPI's own, more specific
    handling of ordinary domain errors (still a plain 401 here, not 500).
    """
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}
