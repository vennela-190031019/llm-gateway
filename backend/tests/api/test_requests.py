from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_request import LLMRequest, LLMRequestStatus
from app.repositories.llm_request_repository import LLMRequestRepository


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "hunter22"}
    )
    return str(response.json()["access_token"])


async def _current_user_id(client: AsyncClient, token: str) -> uuid.UUID:
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return uuid.UUID(response.json()["id"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_request(
    db_session: AsyncSession,
    *,
    user_id: uuid.UUID,
    model: str = "gpt-4o-mini",
    provider: str | None = "openai",
    input_tokens: int = 10,
    output_tokens: int = 5,
    estimated_cost: str | None = "0.001200",
    latency_ms: float = 100.0,
    status: LLMRequestStatus = LLMRequestStatus.SUCCESS,
    cache_hit: bool = False,
    error: str | None = None,
    created_at: datetime | None = None,
) -> LLMRequest:
    record = LLMRequest(
        user_id=user_id,
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost=Decimal(estimated_cost) if estimated_cost is not None else None,
        latency_ms=latency_ms,
        status=status,
        cache_hit=cache_hit,
        error=error,
    )
    if created_at is not None:
        record.created_at = created_at
    await LLMRequestRepository(db_session).create(record)
    await db_session.commit()
    return record


async def test_list_requests_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/requests")
    assert response.status_code == 401


async def test_list_requests_returns_only_current_users_requests(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token_a = await _register_and_login(client, "requester-a@example.com")
    user_a = await _current_user_id(client, token_a)
    token_b = await _register_and_login(client, "requester-b@example.com")
    user_b = await _current_user_id(client, token_b)

    await _create_request(db_session, user_id=user_a, model="gpt-4o-mini")
    await _create_request(db_session, user_id=user_b, model="llama3.1")

    response = await client.get("/api/v1/requests", headers=_auth_headers(token_a))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["model"] == "gpt-4o-mini"


async def test_list_requests_orders_most_recent_first_and_respects_limit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _register_and_login(client, "orderer@example.com")
    user_id = await _current_user_id(client, token)
    now = datetime.now(UTC)

    await _create_request(
        db_session, user_id=user_id, model="oldest", created_at=now - timedelta(minutes=10)
    )
    await _create_request(
        db_session, user_id=user_id, model="middle", created_at=now - timedelta(minutes=5)
    )
    await _create_request(db_session, user_id=user_id, model="newest", created_at=now)

    response = await client.get(
        "/api/v1/requests", params={"limit": 2}, headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["model"] for item in body] == ["newest", "middle"]


async def test_get_request_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/requests/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_get_request_returns_full_detail_including_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _register_and_login(client, "detail-getter@example.com")
    user_id = await _current_user_id(client, token)
    record = await _create_request(
        db_session,
        user_id=user_id,
        status=LLMRequestStatus.ERROR,
        error="all providers exhausted",
        estimated_cost=None,
    )

    response = await client.get(
        f"/api/v1/requests/{record.request_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == str(record.request_id)
    assert body["status"] == "error"
    assert body["error"] == "all providers exhausted"
    assert body["estimated_cost"] is None


async def test_get_request_returns_404_for_unknown_id(client: AsyncClient) -> None:
    token = await _register_and_login(client, "detail-404@example.com")

    response = await client.get(f"/api/v1/requests/{uuid.uuid4()}", headers=_auth_headers(token))

    assert response.status_code == 404


async def test_get_request_returns_404_for_another_users_request(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token_a = await _register_and_login(client, "owner@example.com")
    owner_id = await _current_user_id(client, token_a)
    token_b = await _register_and_login(client, "intruder@example.com")
    record = await _create_request(db_session, user_id=owner_id)

    response = await client.get(
        f"/api/v1/requests/{record.request_id}", headers=_auth_headers(token_b)
    )

    assert response.status_code == 404


async def test_summary_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/requests/summary")
    assert response.status_code == 401


async def test_summary_with_no_requests_returns_nulls(client: AsyncClient) -> None:
    token = await _register_and_login(client, "empty-summary@example.com")

    response = await client.get("/api/v1/requests/summary", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 0
    assert body["success_rate"] is None
    assert body["average_latency_ms"] is None
    assert body["total_tokens"] == 0
    assert float(body["total_cost"]) == 0
    assert body["cache_hit_rate"] is None


async def test_summary_computes_correct_aggregates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _register_and_login(client, "summary-tester@example.com")
    user_id = await _current_user_id(client, token)

    await _create_request(
        db_session,
        user_id=user_id,
        status=LLMRequestStatus.SUCCESS,
        cache_hit=True,
        latency_ms=100.0,
        input_tokens=10,
        output_tokens=10,
        estimated_cost="0.01",
    )
    await _create_request(
        db_session,
        user_id=user_id,
        status=LLMRequestStatus.SUCCESS,
        cache_hit=False,
        latency_ms=300.0,
        input_tokens=5,
        output_tokens=5,
        estimated_cost="0.02",
    )
    await _create_request(
        db_session,
        user_id=user_id,
        status=LLMRequestStatus.ERROR,
        cache_hit=False,
        latency_ms=500.0,
        input_tokens=0,
        output_tokens=0,
        estimated_cost=None,
    )

    response = await client.get("/api/v1/requests/summary", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 3
    assert body["success_rate"] == pytest.approx(200 / 3)
    assert body["average_latency_ms"] == pytest.approx(300.0)
    assert body["total_tokens"] == 30
    assert float(body["total_cost"]) == pytest.approx(0.03)
    assert body["cache_hit_rate"] == pytest.approx(100 / 3)
