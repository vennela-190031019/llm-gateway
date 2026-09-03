"""Tests for slowapi rate limiting — see app.core.rate_limit and the
@limiter.limit(...) decorators throughout app.api.v1.*.

Rate limiting is disabled by default for the whole suite (see the
autouse `_disable_rate_limiting` fixture in tests/conftest.py) — these
tests deliberately re-enable it, and reset the limiter's counters before
and after, so they don't leak state into any other test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.rate_limit import AUTH_RATE_LIMIT, limiter


@pytest.fixture(autouse=True)
def _enable_rate_limiting() -> Iterator[None]:
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "hunter22"}
    )
    return str(response.json()["access_token"])


def _auth_limit_count() -> int:
    return int(AUTH_RATE_LIMIT.split("/")[0])


async def test_register_returns_429_after_exceeding_auth_rate_limit(
    client: AsyncClient,
) -> None:
    limit = _auth_limit_count()
    for i in range(limit):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": f"register-limit-{i}@example.com", "password": "hunter22"},
        )
        assert response.status_code == 201

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "one-too-many@example.com", "password": "hunter22"},
    )

    assert response.status_code == 429
    body = response.json()
    assert "Rate limit exceeded" in body["detail"]


async def test_login_returns_429_after_exceeding_auth_rate_limit(client: AsyncClient) -> None:
    limit = _auth_limit_count()
    for _ in range(limit):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "wrong"},
    )

    assert response.status_code == 429


async def test_default_rate_limit_applies_to_a_plain_endpoint(client: AsyncClient) -> None:
    """Confirms the *default* limit (not just the auth-specific one)
    actually applies broadly, via the per-route @limiter.limit(...)
    decorator on GET /models — see app.core.rate_limit's module
    docstring for why every route needs that decorator explicitly rather
    than a blanket middleware. /healthz is deliberately exempt from rate
    limiting (see the same docstring), so this uses /models instead.
    """
    limit = get_settings().rate_limit_per_minute
    token = await _register_and_login(client, "default-limit@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(limit):
        response = await client.get("/api/v1/models", headers=headers)
        assert response.status_code == 200

    response = await client.get("/api/v1/models", headers=headers)

    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]
