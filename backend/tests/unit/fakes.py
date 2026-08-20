"""Shared test doubles for the provider layer. Not a test module itself."""

from __future__ import annotations

from app.providers.base import LLMProvider
from app.providers.exceptions import ProviderError
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse, FinishReason


def make_response(*, provider: str, model: str, content: str = "ok") -> ChatCompletionResponse:
    return ChatCompletionResponse(
        provider=provider,
        model=model,
        content=content,
        input_tokens=1,
        output_tokens=1,
        finish_reason=FinishReason.STOP,
        latency_ms=0.0,
    )


class FakeProvider(LLMProvider):
    """Replays a fixed sequence of outcomes (responses or exceptions)."""

    def __init__(
        self, name: str, outcomes: list[ChatCompletionResponse | ProviderError]
    ) -> None:
        self.name = name
        self._outcomes = list(outcomes)
        self.calls = 0

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        self.calls += 1
        if not self._outcomes:
            raise AssertionError(f"{self.name} provider called more times than expected")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, ProviderError):
            raise outcome
        return outcome
