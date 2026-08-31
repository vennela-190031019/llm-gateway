from __future__ import annotations

from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "hunter22"}
    )
    return str(response.json()["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_template(client: AsyncClient, token: str, name: str) -> None:
    response = await client.post(
        "/api/v1/prompts", json={"name": name}, headers=_auth_headers(token)
    )
    assert response.status_code == 201


async def _create_version(
    client: AsyncClient,
    token: str,
    name: str,
    *,
    template_text: str,
    variables: list[str],
    model: str = "gpt-4o-mini",
    temperature: float = 0.5,
) -> None:
    response = await client.post(
        f"/api/v1/prompts/{name}/versions",
        json={
            "template_text": template_text,
            "variables": variables,
            "model": model,
            "temperature": temperature,
        },
        headers=_auth_headers(token),
    )
    assert response.status_code == 201


async def test_create_template_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/prompts", json={"name": "x"})
    assert response.status_code == 401


async def test_create_template(client: AsyncClient) -> None:
    token = await _register_and_login(client, "author@example.com")

    response = await client.post(
        "/api/v1/prompts",
        json={"name": "customer-support", "description": "Support replies"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "customer-support"
    assert body["description"] == "Support replies"


async def test_create_template_rejects_duplicate_name(client: AsyncClient) -> None:
    token = await _register_and_login(client, "dupe-author@example.com")
    await _create_template(client, token, "dupe")

    response = await client.post(
        "/api/v1/prompts", json={"name": "dupe"}, headers=_auth_headers(token)
    )

    assert response.status_code == 400


async def test_create_version_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/prompts/anything/versions",
        json={"template_text": "hi", "variables": [], "model": "gpt-4o-mini"},
    )
    assert response.status_code == 401


async def test_create_version_and_get_template_detail(client: AsyncClient) -> None:
    token = await _register_and_login(client, "versioner@example.com")
    await _create_template(client, token, "greeting")

    version_response = await client.post(
        "/api/v1/prompts/greeting/versions",
        json={
            "template_text": "Hi {name}",
            "variables": ["name"],
            "model": "gpt-4o-mini",
            "temperature": 0.5,
        },
        headers=_auth_headers(token),
    )

    assert version_response.status_code == 201
    assert version_response.json()["version"] == 1
    assert version_response.json()["is_active"] is True

    detail_response = await client.get("/api/v1/prompts/greeting", headers=_auth_headers(token))
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["name"] == "greeting"
    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["version"] == 1


async def test_get_template_returns_404_for_unknown_name(client: AsyncClient) -> None:
    token = await _register_and_login(client, "getter-404@example.com")

    response = await client.get("/api/v1/prompts/ghost", headers=_auth_headers(token))

    assert response.status_code == 404


async def test_create_version_for_unknown_template_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "ghost-author@example.com")

    response = await client.post(
        "/api/v1/prompts/ghost/versions",
        json={"template_text": "hi", "variables": [], "model": "gpt-4o-mini"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_list_templates_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/prompts")
    assert response.status_code == 401


async def test_list_templates(client: AsyncClient) -> None:
    token = await _register_and_login(client, "lister@example.com")
    await _create_template(client, token, "listed-one")

    response = await client.get("/api/v1/prompts", headers=_auth_headers(token))

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "listed-one" in names


async def test_render_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/prompts/anything/render")
    assert response.status_code == 401


async def test_render_via_query_params(client: AsyncClient) -> None:
    token = await _register_and_login(client, "renderer@example.com")
    await _create_template(client, token, "greeting")
    await _create_version(
        client,
        token,
        "greeting",
        template_text="Hi {name}, welcome to {place}!",
        variables=["name", "place"],
    )

    response = await client.get(
        "/api/v1/prompts/greeting/render",
        params={"name": "Ada", "place": "the lab"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Hi Ada, welcome to the lab!"
    assert body["model"] == "gpt-4o-mini"
    assert body["version"] == 1


async def test_render_via_body(client: AsyncClient) -> None:
    token = await _register_and_login(client, "body-renderer@example.com")
    await _create_template(client, token, "greeting")
    await _create_version(
        client, token, "greeting", template_text="Hi {name}", variables=["name"]
    )

    response = await client.request(
        "GET",
        "/api/v1/prompts/greeting/render",
        json={"variables": {"name": "Ada"}},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Hi Ada"


async def test_render_missing_variables_returns_422(client: AsyncClient) -> None:
    token = await _register_and_login(client, "incomplete@example.com")
    await _create_template(client, token, "greeting")
    await _create_version(
        client,
        token,
        "greeting",
        template_text="Hi {name}, welcome to {place}!",
        variables=["name", "place"],
    )

    response = await client.get(
        "/api/v1/prompts/greeting/render",
        params={"name": "Ada"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_render_unknown_template_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "renderer-404@example.com")

    response = await client.get("/api/v1/prompts/ghost/render", headers=_auth_headers(token))

    assert response.status_code == 404


async def test_render_unknown_version_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "renderer-bad-version@example.com")
    await _create_template(client, token, "greeting")
    await _create_version(
        client, token, "greeting", template_text="Hi {name}", variables=["name"]
    )

    response = await client.get(
        "/api/v1/prompts/greeting/render",
        params={"name": "Ada", "version": 99},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_activate_version_changes_render_output(client: AsyncClient) -> None:
    token = await _register_and_login(client, "activator@example.com")
    await _create_template(client, token, "greeting")
    await _create_version(
        client, token, "greeting", template_text="Hi {name}", variables=["name"]
    )
    await _create_version(
        client,
        token,
        "greeting",
        template_text="Hello there, {name}!",
        variables=["name"],
        model="gpt-4o",
        temperature=0.9,
    )

    activate_response = await client.patch(
        "/api/v1/prompts/greeting/versions/2/activate", headers=_auth_headers(token)
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True

    render_response = await client.get(
        "/api/v1/prompts/greeting/render",
        params={"name": "Ada"},
        headers=_auth_headers(token),
    )

    assert render_response.json()["content"] == "Hello there, Ada!"
    assert render_response.json()["version"] == 2


async def test_activate_version_requires_authentication(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/prompts/anything/versions/1/activate")
    assert response.status_code == 401


async def test_activate_unknown_version_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "activator-404@example.com")
    await _create_template(client, token, "greeting")

    response = await client.patch(
        "/api/v1/prompts/greeting/versions/1/activate", headers=_auth_headers(token)
    )

    assert response.status_code == 404
