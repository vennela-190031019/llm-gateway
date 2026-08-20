"""Unit tests for OpenAIProvider.

The AsyncOpenAI client is mocked throughout — no live network calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import httpx2
import openai
import pytest
from openai import AsyncOpenAI

from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.openai_provider import OpenAIProvider
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatRole, FinishReason


def _request(**overrides: object) -> ChatCompletionRequest:
    defaults: dict[str, object] = {
        "model": "gpt-4o-mini",
        "messages": [ChatMessage(role=ChatRole.USER, content="hello")],
    }
    defaults.update(overrides)
    return ChatCompletionRequest(**defaults)  # type: ignore[arg-type]


def _fake_completion(
    *, content: str | None = "hi there", finish_reason: str = "stop"
) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    return SimpleNamespace(choices=[choice], usage=usage, model="gpt-4o-mini")


def _provider(mock_client: AsyncMock) -> OpenAIProvider:
    return OpenAIProvider(client=cast(AsyncOpenAI, mock_client))


def _dummy_request_exc() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")


def _dummy_response_exc(status_code: int) -> httpx2.Response:
    return httpx2.Response(status_code, request=_dummy_request_exc(), json={})


async def test_complete_returns_normalized_response() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _fake_completion()
    provider = _provider(mock_client)

    result = await provider.complete(_request())

    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.content == "hi there"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.finish_reason == FinishReason.STOP
    assert result.latency_ms >= 0


async def test_complete_maps_finish_reason() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _fake_completion(finish_reason="length")
    provider = _provider(mock_client)

    result = await provider.complete(_request())

    assert result.finish_reason == FinishReason.LENGTH


async def test_complete_omits_max_tokens_when_not_set() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _fake_completion()
    provider = _provider(mock_client)

    await provider.complete(_request())

    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["max_tokens"] is openai.omit


async def test_complete_passes_max_tokens_when_set() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _fake_completion()
    provider = _provider(mock_client)

    await provider.complete(_request(max_tokens=256))

    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["max_tokens"] == 256


async def test_complete_maps_timeout_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = openai.APITimeoutError(
        request=_dummy_request_exc()
    )
    provider = _provider(mock_client)

    with pytest.raises(ProviderTimeoutError):
        await provider.complete(_request())


async def test_complete_maps_connection_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = openai.APIConnectionError(
        request=_dummy_request_exc()
    )
    provider = _provider(mock_client)

    with pytest.raises(ProviderUnavailableError):
        await provider.complete(_request())


async def test_complete_maps_rate_limit_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = openai.RateLimitError(
        "rate limited", response=_dummy_response_exc(429), body=None
    )
    provider = _provider(mock_client)

    with pytest.raises(ProviderRateLimitError):
        await provider.complete(_request())


async def test_complete_maps_authentication_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
        "bad key", response=_dummy_response_exc(401), body=None
    )
    provider = _provider(mock_client)

    with pytest.raises(ProviderAuthenticationError):
        await provider.complete(_request())


async def test_complete_maps_generic_status_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = openai.APIStatusError(
        "server error", response=_dummy_response_exc(500), body=None
    )
    provider = _provider(mock_client)

    with pytest.raises(ProviderError):
        await provider.complete(_request())


async def test_complete_maps_empty_choices_to_response_error() -> None:
    mock_client = AsyncMock()
    completion = _fake_completion()
    completion.choices = []
    mock_client.chat.completions.create.return_value = completion
    provider = _provider(mock_client)

    with pytest.raises(ProviderResponseError):
        await provider.complete(_request())


async def test_complete_maps_null_content_to_response_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _fake_completion(content=None)
    provider = _provider(mock_client)

    with pytest.raises(ProviderResponseError):
        await provider.complete(_request())


async def test_complete_maps_missing_usage_to_response_error() -> None:
    mock_client = AsyncMock()
    completion = _fake_completion()
    completion.usage = None
    mock_client.chat.completions.create.return_value = completion
    provider = _provider(mock_client)

    with pytest.raises(ProviderResponseError):
        await provider.complete(_request())
