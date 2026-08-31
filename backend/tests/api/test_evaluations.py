from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import fallback as fallback_module

from ..unit.fakes import FakeProvider, make_response


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "hunter22"}
    )
    return str(response.json()["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_dataset(client: AsyncClient, token: str, name: str) -> str:
    response = await client.post(
        "/api/v1/evaluations/datasets", json={"name": name}, headers=_auth_headers(token)
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _add_case(
    client: AsyncClient,
    token: str,
    dataset_id: str,
    *,
    input: str,
    expected_output: str | None,
) -> None:
    response = await client.post(
        f"/api/v1/evaluations/datasets/{dataset_id}/cases",
        json={"input": input, "expected_output": expected_output},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201


async def test_create_dataset_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/evaluations/datasets", json={"name": "x"})
    assert response.status_code == 401


async def test_create_dataset(client: AsyncClient) -> None:
    token = await _register_and_login(client, "author@example.com")

    response = await client.post(
        "/api/v1/evaluations/datasets",
        json={"name": "geography", "description": "Capital cities"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "geography"
    assert body["description"] == "Capital cities"


async def test_create_dataset_rejects_duplicate_name(client: AsyncClient) -> None:
    token = await _register_and_login(client, "dupe-author@example.com")
    await _create_dataset(client, token, "dupe")

    response = await client.post(
        "/api/v1/evaluations/datasets", json={"name": "dupe"}, headers=_auth_headers(token)
    )

    assert response.status_code == 400


async def test_add_case_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/evaluations/datasets/00000000-0000-0000-0000-000000000000/cases",
        json={"input": "hi"},
    )
    assert response.status_code == 401


async def test_add_case(client: AsyncClient) -> None:
    token = await _register_and_login(client, "caser@example.com")
    dataset_id = await _create_dataset(client, token, "geography")

    response = await client.post(
        f"/api/v1/evaluations/datasets/{dataset_id}/cases",
        json={"input": "What is the capital of France?", "expected_output": "Paris"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["input"] == "What is the capital of France?"
    assert body["expected_output"] == "Paris"


async def test_add_case_for_unknown_dataset_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "caser-404@example.com")

    response = await client.post(
        "/api/v1/evaluations/datasets/00000000-0000-0000-0000-000000000000/cases",
        json={"input": "hi"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_list_datasets_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/evaluations/datasets")
    assert response.status_code == 401


async def test_list_datasets(client: AsyncClient) -> None:
    token = await _register_and_login(client, "lister@example.com")
    await _create_dataset(client, token, "listed-one")

    response = await client.get("/api/v1/evaluations/datasets", headers=_auth_headers(token))

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "listed-one" in names


async def test_start_run_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/evaluations/runs",
        json={
            "dataset_id": "00000000-0000-0000-0000-000000000000",
            "model": "gpt-4o-mini",
            "provider": "openai",
            "metrics": ["exact_match"],
        },
    )
    assert response.status_code == 401


async def test_start_run_for_unknown_dataset_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "runner-404@example.com")

    response = await client.post(
        "/api/v1/evaluations/runs",
        json={
            "dataset_id": "00000000-0000-0000-0000-000000000000",
            "model": "gpt-4o-mini",
            "provider": "openai",
            "metrics": ["exact_match"],
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_start_run_with_unknown_metric_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _register_and_login(client, "runner-bad-metric@example.com")
    dataset_id = await _create_dataset(client, token, "geography")
    await _add_case(client, token, dataset_id, input="hi", expected_output="hi")

    response = await client.post(
        "/api/v1/evaluations/runs",
        json={
            "dataset_id": dataset_id,
            "model": "gpt-4o-mini",
            "provider": "openai",
            "metrics": ["not-a-real-metric"],
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 400


async def test_start_run_executes_and_returns_summary(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="Paris")]
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: fake_provider)

    token = await _register_and_login(client, "runner@example.com")
    dataset_id = await _create_dataset(client, token, "geography")
    await _add_case(
        client, token, dataset_id, input="What is the capital of France?", expected_output="Paris"
    )

    response = await client.post(
        "/api/v1/evaluations/runs",
        json={
            "dataset_id": dataset_id,
            "model": "gpt-4o-mini",
            "provider": "openai",
            "metrics": ["exact_match"],
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["case_count"] == 1
    assert body["average_scores"] == {"exact_match": 1.0}
    assert body["completed_at"] is not None


async def test_get_run_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/evaluations/runs/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 401


async def test_get_run_returns_404_for_unknown_run(client: AsyncClient) -> None:
    token = await _register_and_login(client, "getter-404@example.com")

    response = await client.get(
        "/api/v1/evaluations/runs/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_get_run_returns_summary(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="Paris")]
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: fake_provider)

    token = await _register_and_login(client, "get-runner@example.com")
    dataset_id = await _create_dataset(client, token, "geography")
    await _add_case(
        client, token, dataset_id, input="What is the capital of France?", expected_output="Paris"
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
    run_id = run_response.json()["id"]

    response = await client.get(
        f"/api/v1/evaluations/runs/{run_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == run_id
    assert response.json()["status"] == "completed"


async def test_list_run_results_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/evaluations/runs/00000000-0000-0000-0000-000000000000/results"
    )
    assert response.status_code == 401


async def test_list_run_results_returns_404_for_unknown_run(client: AsyncClient) -> None:
    token = await _register_and_login(client, "results-404@example.com")

    response = await client.get(
        "/api/v1/evaluations/runs/00000000-0000-0000-0000-000000000000/results",
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_list_run_results(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini", content="Paris")]
    )
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: fake_provider)

    token = await _register_and_login(client, "results-lister@example.com")
    dataset_id = await _create_dataset(client, token, "geography")
    await _add_case(
        client, token, dataset_id, input="What is the capital of France?", expected_output="Paris"
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
    run_id = run_response.json()["id"]

    response = await client.get(
        f"/api/v1/evaluations/runs/{run_id}/results", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["actual_output"] == "Paris"
    assert results[0]["scores"] == {"exact_match": 1.0}
