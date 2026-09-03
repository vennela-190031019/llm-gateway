"""Input-validation edge case tests — exercises the bounds added to
app/schemas/*.py in the Phase 11 schema audit, plus the request
body-size limit (app.core.middleware.MaxBodySizeMiddleware).
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.config import get_settings


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "hunter22"}
    )
    return str(response.json()["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_register_rejects_oversized_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": f"{'a' * 320}@example.com", "password": "hunter22"},
    )

    assert response.status_code == 422


async def test_chat_completion_rejects_oversized_message_content(client: AsyncClient) -> None:
    token = await _register_and_login(client, "validation-content@example.com")

    response = await client.post(
        "/api/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "A" * 50_001}]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_chat_completion_rejects_temperature_out_of_range(client: AsyncClient) -> None:
    token = await _register_and_login(client, "validation-temp@example.com")

    response = await client.post(
        "/api/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 2.5,
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_chat_completion_rejects_max_tokens_out_of_range(client: AsyncClient) -> None:
    token = await _register_and_login(client, "validation-maxtok@example.com")

    response = await client.post(
        "/api/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 100_000,
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_chat_completion_rejects_too_many_messages(client: AsyncClient) -> None:
    token = await _register_and_login(client, "validation-nmsg@example.com")

    response = await client.post(
        "/api/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}] * 101,
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_prompt_template_rejects_oversized_description(
    client: AsyncClient,
) -> None:
    token = await _register_and_login(client, "validation-prompt-desc@example.com")

    response = await client.post(
        "/api/v1/prompts",
        json={"name": "oversized-desc", "description": "A" * 2001},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_prompt_version_rejects_oversized_template_text(
    client: AsyncClient,
) -> None:
    token = await _register_and_login(client, "validation-prompt-text@example.com")
    await client.post(
        "/api/v1/prompts", json={"name": "big-template"}, headers=_auth_headers(token)
    )

    response = await client.post(
        "/api/v1/prompts/big-template/versions",
        json={"template_text": "A" * 50_001, "variables": [], "model": "gpt-4o-mini"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_prompt_version_rejects_temperature_out_of_range(
    client: AsyncClient,
) -> None:
    token = await _register_and_login(client, "validation-prompt-temp@example.com")
    await client.post("/api/v1/prompts", json={"name": "bad-temp"}, headers=_auth_headers(token))

    response = await client.post(
        "/api/v1/prompts/bad-temp/versions",
        json={
            "template_text": "hi",
            "variables": [],
            "model": "gpt-4o-mini",
            "temperature": -1,
        },
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_create_evaluation_dataset_rejects_oversized_description(
    client: AsyncClient,
) -> None:
    token = await _register_and_login(client, "validation-eval-desc@example.com")

    response = await client.post(
        "/api/v1/evaluations/datasets",
        json={"name": "oversized-desc", "description": "A" * 2001},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_request_body_too_large_returns_413(client: AsyncClient) -> None:
    max_bytes = get_settings().max_request_body_bytes
    token = await _register_and_login(client, "validation-bodysize@example.com")

    response = await client.post(
        "/api/v1/chat/completions",
        content=b"x" * (max_bytes + 1),
        headers={**_auth_headers(token), "Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"]
