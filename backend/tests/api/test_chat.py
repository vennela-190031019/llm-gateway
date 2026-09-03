from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import wait_none

from app.api.v1.chat import get_chat_service
from app.main import app
from app.models.llm_model import LLMModel
from app.models.llm_request import LLMRequestStatus
from app.models.provider import Provider
from app.providers.exceptions import ProviderConfigurationError, ProviderTimeoutError
from app.repositories.llm_request_repository import LLMRequestRepository
from app.services import fallback as fallback_module
from app.services.chat_service import ChatCompletionService
from app.services.fallback import FallbackExecutor
from app.services.router import ModelRouter
from tests.unit.fakes import FakeProvider, make_fake_cache_service, make_response


async def _seed_pricing(db_session: AsyncSession) -> None:
    provider = Provider(name="openai", base_url="https://api.openai.com/v1", is_active=True)
    db_session.add(provider)
    await db_session.flush()
    db_session.add(
        LLMModel(
            name="gpt-4o-mini",
            provider_id=provider.id,
            tier="standard",
            input_price_per_1k="0.150000",
            output_price_per_1k="0.600000",
            is_active=True,
        )
    )
    await db_session.commit()


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


def _payload(
    *,
    temperature: float = 1.0,
    model: str = "gpt-4o-mini",
    task_type: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": "hello there"}],
        "temperature": temperature,
    }
    if task_type is not None:
        payload["metadata"] = {"task_type": task_type}
    return payload


async def test_completions_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/chat/completions", json=_payload())
    assert response.status_code == 401


async def test_completions_returns_successful_response_end_to_end(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="hi there")]
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: provider)
    service = ChatCompletionService(
        router=ModelRouter(),
        executor=FallbackExecutor(wait=wait_none()),
        cache=make_fake_cache_service(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    token = await _register_and_login(client, "chatter@example.com")

    try:
        response = await client.post(
            "/api/v1/chat/completions", json=_payload(), headers=_auth_headers(token)
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o-mini"
    assert body["content"] == "hi there"
    assert body["cached"] is False


async def test_completions_serves_cache_hit_on_second_identical_request(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only one outcome queued — a second provider call would raise.
    provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="hi there")]
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: provider)
    service = ChatCompletionService(
        router=ModelRouter(),
        executor=FallbackExecutor(wait=wait_none()),
        cache=make_fake_cache_service(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    token = await _register_and_login(client, "cacher@example.com")
    payload = _payload(temperature=0.0)

    try:
        first = await client.post(
            "/api/v1/chat/completions", json=payload, headers=_auth_headers(token)
        )
        second = await client.post(
            "/api/v1/chat/completions", json=payload, headers=_auth_headers(token)
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert provider.calls == 1


async def test_completions_returns_502_and_logs_failure_when_providers_exhausted(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    openai_provider = FakeProvider("openai", [ProviderTimeoutError("openai", "slow")] * 3)
    ollama_provider = FakeProvider("ollama", [ProviderTimeoutError("ollama", "slow")] * 3)
    monkeypatch.setattr(
        fallback_module,
        "get_provider",
        lambda name: {"openai": openai_provider, "ollama": ollama_provider}[name],
    )
    service = ChatCompletionService(
        router=ModelRouter(),
        executor=FallbackExecutor(wait=wait_none()),
        cache=make_fake_cache_service(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    token = await _register_and_login(client, "unlucky@example.com")
    user_id = await _current_user_id(client, token)

    try:
        response = await client.post(
            "/api/v1/chat/completions",
            json=_payload(task_type="summarization"),
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 502

    records = await LLMRequestRepository(db_session).list_for_user(user_id)
    assert len(records) == 1
    record = records[0]
    assert record.status == LLMRequestStatus.ERROR
    assert record.error is not None
    assert record.provider is None
    assert record.input_tokens == 0
    assert record.estimated_cost is None


async def test_completions_returns_502_when_provider_construction_fails(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for a real bug: OPENAI_API_KEY unset caused
    AsyncOpenAI to raise at construction time, outside the code path that
    catches provider errors — so a request that should have failed over
    to Ollama (or, if every candidate is misconfigured, returned a clean
    502) instead surfaced as an unhandled 500.
    """
    def _get_provider(name: str) -> FakeProvider:
        raise ProviderConfigurationError(name, "missing api key")

    monkeypatch.setattr(fallback_module, "get_provider", _get_provider)
    service = ChatCompletionService(
        router=ModelRouter(),
        executor=FallbackExecutor(wait=wait_none()),
        cache=make_fake_cache_service(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    token = await _register_and_login(client, "misconfigured@example.com")
    user_id = await _current_user_id(client, token)

    try:
        response = await client.post(
            "/api/v1/chat/completions",
            json=_payload(task_type="summarization"),
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 502

    records = await LLMRequestRepository(db_session).list_for_user(user_id)
    assert len(records) == 1
    assert records[0].status == LLMRequestStatus.ERROR


async def test_completions_persists_cost_and_token_usage(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_pricing(db_session)
    provider = FakeProvider(
        "openai",
        [
            make_response(provider="openai", model="gpt-4o-mini", content="hi there")
            .model_copy(update={"input_tokens": 100, "output_tokens": 50})
        ],
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: provider)
    service = ChatCompletionService(
        router=ModelRouter(),
        executor=FallbackExecutor(wait=wait_none()),
        cache=make_fake_cache_service(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    token = await _register_and_login(client, "billed@example.com")
    user_id = await _current_user_id(client, token)

    try:
        response = await client.post(
            "/api/v1/chat/completions",
            json=_payload(),
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200

    records = await LLMRequestRepository(db_session).list_for_user(user_id)
    assert len(records) == 1
    record = records[0]
    assert record.status == LLMRequestStatus.SUCCESS
    assert record.model == "gpt-4o-mini"
    assert record.provider == "openai"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.total_tokens == 150
    # 100/1000 * 0.15 + 50/1000 * 0.60 = 0.015 + 0.03 = 0.045
    assert record.estimated_cost is not None
    assert abs(float(record.estimated_cost) - 0.045) < 1e-9
