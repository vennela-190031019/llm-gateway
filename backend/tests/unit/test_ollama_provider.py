"""Unit tests for OllamaProvider.

The httpx.AsyncClient is mocked throughout — no live network calls.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.ollama_provider import OllamaProvider
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatRole, FinishReason

_REQUEST_STUB = httpx.Request("POST", "http://localhost:11434/api/chat")


def _request(**overrides: object) -> ChatCompletionRequest:
    defaults: dict[str, object] = {
        "model": "llama3",
        "messages": [ChatMessage(role=ChatRole.USER, content="hello")],
    }
    defaults.update(overrides)
    return ChatCompletionRequest(**defaults)  # type: ignore[arg-type]


def _ok_response(*, body: dict[str, object] | None = None) -> httpx.Response:
    payload: dict[str, object] = {
        "model": "llama3",
        "message": {"role": "assistant", "content": "hi there"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 12,
        "eval_count": 6,
    }
    if body is not None:
        payload = body
    return httpx.Response(200, request=_REQUEST_STUB, json=payload)


def _client_with_post(mock_post: AsyncMock) -> httpx.AsyncClient:
    client = MagicMock()
    client.post = mock_post
    return cast(httpx.AsyncClient, client)


def _provider(mock_post: AsyncMock) -> OllamaProvider:
    return OllamaProvider(client=_client_with_post(mock_post))


async def test_complete_returns_normalized_response() -> None:
    mock_post = AsyncMock(return_value=_ok_response())
    provider = _provider(mock_post)

    result = await provider.complete(_request())

    assert result.provider == "ollama"
    assert result.model == "llama3"
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 6
    assert result.finish_reason == FinishReason.STOP
    assert result.latency_ms >= 0


async def test_complete_sends_num_predict_when_max_tokens_set() -> None:
    mock_post = AsyncMock(return_value=_ok_response())
    provider = _provider(mock_post)

    await provider.complete(_request(max_tokens=128))

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["options"]["num_predict"] == 128


async def test_complete_maps_timeout_error() -> None:
    mock_post = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))
    provider = _provider(mock_post)

    with pytest.raises(ProviderTimeoutError):
        await provider.complete(_request())


async def test_complete_maps_connection_error() -> None:
    mock_post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    provider = _provider(mock_post)

    with pytest.raises(ProviderUnavailableError):
        await provider.complete(_request())


async def test_complete_maps_rate_limit_status() -> None:
    mock_post = AsyncMock(
        return_value=httpx.Response(429, request=_REQUEST_STUB, json={"error": "slow down"})
    )
    provider = _provider(mock_post)

    with pytest.raises(ProviderRateLimitError):
        await provider.complete(_request())


async def test_complete_maps_authentication_status() -> None:
    mock_post = AsyncMock(
        return_value=httpx.Response(401, request=_REQUEST_STUB, json={"error": "unauthorized"})
    )
    provider = _provider(mock_post)

    with pytest.raises(ProviderAuthenticationError):
        await provider.complete(_request())


async def test_complete_maps_generic_status_error() -> None:
    mock_post = AsyncMock(
        return_value=httpx.Response(500, request=_REQUEST_STUB, json={"error": "boom"})
    )
    provider = _provider(mock_post)

    with pytest.raises(ProviderError):
        await provider.complete(_request())


async def test_complete_maps_malformed_response_to_response_error() -> None:
    mock_post = AsyncMock(return_value=_ok_response(body={"unexpected": "shape"}))
    provider = _provider(mock_post)

    with pytest.raises(ProviderResponseError):
        await provider.complete(_request())


async def test_complete_maps_non_json_body_to_response_error() -> None:
    mock_post = AsyncMock(
        return_value=httpx.Response(200, request=_REQUEST_STUB, content=b"not json")
    )
    provider = _provider(mock_post)

    with pytest.raises(ProviderResponseError):
        await provider.complete(_request())
