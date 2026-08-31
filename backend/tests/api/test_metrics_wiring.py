"""Confirms Prometheus metrics actually increment on real requests through
the full app (not just that the right function was called) — covers the
Phase 9 audit: HTTP-level metrics, chat completions, per-candidate
fallback failures, and evaluation runs (previously unwired).

Metrics are module-level singletons shared across the whole test
session, so every assertion here compares a before/after delta rather
than an absolute value.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from prometheus_client import REGISTRY, generate_latest
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import wait_none

from app.api.v1.chat import get_chat_service
from app.main import app
from app.models.llm_model import LLMModel
from app.models.provider import Provider
from app.providers.exceptions import ProviderTimeoutError
from app.services import fallback as fallback_module
from app.services.chat_service import ChatCompletionService
from app.services.fallback import FallbackExecutor
from app.services.router import ModelRouter
from tests.unit.fakes import FakeProvider, make_fake_cache_service, make_response


def _metric_value(name: str, labels: dict[str, str]) -> float:
    """Look up one exposition sample by its exact name (e.g.
    "llm_cost_total", "http_request_duration_seconds_count") and label
    set. Matches on `sample.name`, not `family.name` — the parser groups
    samples into families under a name with counter/histogram suffixes
    stripped (e.g. family "llm_cost" for sample "llm_cost_total"), which
    isn't the name we want to key lookups on here.
    """
    text = generate_latest(REGISTRY).decode("utf-8")
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if sample.name == name and sample.labels == labels:
                return sample.value
    return 0.0


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


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_http_metrics_increment_on_a_real_request(client: AsyncClient) -> None:
    labels = {"method": "GET", "path": "/api/v1/healthz", "status_code": "200"}
    before = _metric_value("http_requests_total", labels)

    response = await client.get("/api/v1/healthz")

    assert response.status_code == 200
    after = _metric_value("http_requests_total", labels)
    assert after == before + 1

    duration_count = _metric_value(
        "http_request_duration_seconds_count", {"method": "GET", "path": "/api/v1/healthz"}
    )
    assert duration_count >= 1


async def test_llm_metrics_increment_on_chat_completion(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_pricing(db_session)
    provider = FakeProvider(
        "openai",
        [
            make_response(provider="openai", model="gpt-4o-mini", content="hi")
            .model_copy(update={"input_tokens": 10, "output_tokens": 5})
        ],
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: provider)
    service = ChatCompletionService(
        router=ModelRouter(),
        executor=FallbackExecutor(wait=wait_none()),
        cache=make_fake_cache_service(),
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    token = await _register_and_login(client, "metrics-chatter@example.com")

    requests_before = _metric_value(
        "llm_requests_total", {"model": "gpt-4o-mini", "provider": "openai", "status": "success"}
    )
    tokens_before = _metric_value(
        "llm_tokens_total", {"model": "gpt-4o-mini", "provider": "openai", "type": "input"}
    )
    cost_total_before = _metric_value(
        "llm_cost_total", {"model": "gpt-4o-mini", "provider": "openai"}
    )

    try:
        response = await client.post(
            "/api/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 1.0,
            },
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200

    requests_after = _metric_value(
        "llm_requests_total", {"model": "gpt-4o-mini", "provider": "openai", "status": "success"}
    )
    tokens_after = _metric_value(
        "llm_tokens_total", {"model": "gpt-4o-mini", "provider": "openai", "type": "input"}
    )
    cost_total_after = _metric_value(
        "llm_cost_total", {"model": "gpt-4o-mini", "provider": "openai"}
    )

    assert requests_after == requests_before + 1
    assert tokens_after == tokens_before + 10
    assert cost_total_after > cost_total_before


async def test_llm_errors_total_recorded_per_candidate_on_fallback(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the Phase 9 audit fix: a candidate that fails
    but is rescued by fallback must still show up in llm_errors_total —
    previously only the aggregate `AllProvidersExhaustedError` case (when
    *every* candidate fails) was ever recorded.
    """
    openai_provider = FakeProvider("openai", [ProviderTimeoutError("openai", "slow")] * 3)
    ollama_provider = FakeProvider("ollama", [make_response(provider="ollama", model="llama3.1")])
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
    token = await _register_and_login(client, "fallback-metrics@example.com")

    errors_before = _metric_value(
        "llm_errors_total",
        {"model": "gpt-4o-mini", "provider": "openai", "error_type": "ProviderTimeoutError"},
    )

    try:
        response = await client.post(
            "/api/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 1.0,
                "metadata": {"task_type": "summarization"},
            },
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"

    errors_after = _metric_value(
        "llm_errors_total",
        {"model": "gpt-4o-mini", "provider": "openai", "error_type": "ProviderTimeoutError"},
    )
    assert errors_after == errors_before + 1


async def test_llm_metrics_increment_on_evaluation_run(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the Phase 9 audit fix: evaluation_service.py
    previously called the LLM without reporting any metrics at all.
    """
    await _seed_pricing(db_session)
    provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="Paris")]
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: provider)
    token = await _register_and_login(client, "metrics-evaluator@example.com")

    dataset_response = await client.post(
        "/api/v1/evaluations/datasets",
        json={"name": "geography-metrics"},
        headers=_auth_headers(token),
    )
    dataset_id = dataset_response.json()["id"]
    await client.post(
        f"/api/v1/evaluations/datasets/{dataset_id}/cases",
        json={"input": "What is the capital of France?", "expected_output": "Paris"},
        headers=_auth_headers(token),
    )

    requests_before = _metric_value(
        "llm_requests_total", {"model": "gpt-4o-mini", "provider": "openai", "status": "success"}
    )
    cost_total_before = _metric_value(
        "llm_cost_total", {"model": "gpt-4o-mini", "provider": "openai"}
    )

    run_response = await client.post(
        "/api/v1/evaluations/runs",
        json={
            "dataset_id": dataset_id,
            "model": "gpt-4o-mini",
            "provider": "openai",
            "metrics": ["exact_match"],
        },
        headers=_auth_headers(token),
    )

    assert run_response.status_code == 201

    requests_after = _metric_value(
        "llm_requests_total", {"model": "gpt-4o-mini", "provider": "openai", "status": "success"}
    )
    cost_total_after = _metric_value(
        "llm_cost_total", {"model": "gpt-4o-mini", "provider": "openai"}
    )

    assert requests_after == requests_before + 1
    assert cost_total_after > cost_total_before
