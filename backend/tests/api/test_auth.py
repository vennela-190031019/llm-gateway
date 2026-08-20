from __future__ import annotations

from httpx import AsyncClient

from app.models.user import UserRole


async def _register(client: AsyncClient, email: str, password: str = "hunter22") -> dict:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _login(client: AsyncClient, email: str, password: str = "hunter22") -> str:
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_first_registered_user_is_admin(client: AsyncClient) -> None:
    user = await _register(client, "founder@example.com")
    assert user["role"] == UserRole.ADMIN.value


async def test_subsequent_registered_users_are_plain_users(client: AsyncClient) -> None:
    await _register(client, "founder@example.com")
    second = await _register(client, "teammate@example.com")
    assert second["role"] == UserRole.USER.value


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    await _register(client, "dupe@example.com")
    response = await client.post(
        "/api/v1/auth/register", json={"email": "dupe@example.com", "password": "hunter22"}
    )
    assert response.status_code == 400


async def test_login_returns_bearer_token(client: AsyncClient) -> None:
    await _register(client, "login@example.com")
    token = await _login(client, "login@example.com")
    assert token


async def test_login_rejects_wrong_password(client: AsyncClient) -> None:
    await _register(client, "wrongpw@example.com")
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "wrongpw@example.com", "password": "not-the-password"},
    )
    assert response.status_code == 401


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client: AsyncClient) -> None:
    await _register(client, "whoami@example.com")
    token = await _login(client, "whoami@example.com")
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "whoami@example.com"


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
