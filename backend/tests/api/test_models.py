from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LLMModel
from app.models.provider import Provider


async def _seed_model(db_session: AsyncSession) -> None:
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
    db_session.add(
        LLMModel(
            name="retired-model",
            provider_id=provider.id,
            tier="standard",
            input_price_per_1k="1.000000",
            output_price_per_1k="2.000000",
            is_active=False,
        )
    )
    await db_session.commit()


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "hunter22"}
    )
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "hunter22"}
    )
    return str(response.json()["access_token"])


async def test_list_models_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/models")
    assert response.status_code == 401


async def test_list_models_returns_only_active_models(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_model(db_session)
    token = await _register_and_login(client, "browser@example.com")

    response = await client.get(
        "/api/v1/models", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "gpt-4o-mini"
    assert body[0]["provider_name"] == "openai"
