from __future__ import annotations

import pytest

from app.providers.base import LLMProvider
from app.providers.exceptions import ProviderError, ProviderTimeoutError
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    FinishReason,
)


class _StubProvider(LLMProvider):
    name = "stub"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            provider=self.name,
            model=request.model,
            content="ok",
            input_tokens=1,
            output_tokens=1,
            finish_reason=FinishReason.STOP,
            latency_ms=0.0,
        )


def _request() -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="test-model", messages=[ChatMessage(role=ChatRole.USER, content="hi")]
    )


async def test_stream_raises_not_implemented_by_default() -> None:
    provider = _StubProvider()

    with pytest.raises(NotImplementedError):
        async for _ in provider.stream(_request()):
            pass


def test_provider_error_carries_provider_name_and_message() -> None:
    error = ProviderTimeoutError("openai", "took too long")

    assert isinstance(error, ProviderError)
    assert error.provider == "openai"
    assert error.message == "took too long"
    assert "openai" in str(error)
    assert "took too long" in str(error)
