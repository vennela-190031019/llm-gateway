"""Shared test doubles for the provider and cache layers. Not a test module itself."""

from __future__ import annotations

import fakeredis.aioredis as fakeredis

from app.providers.base import LLMProvider
from app.providers.exceptions import ProviderError
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse, FinishReason
from app.services.cache import CacheService


def make_fake_cache_service(
    *, ttl_seconds: int = 60, temperature_threshold: float = 0.0
) -> CacheService:
    """A CacheService backed by an isolated in-memory fake Redis instance."""
    client = fakeredis.FakeRedis(decode_responses=True)
    return CacheService(
        client=client, ttl_seconds=ttl_seconds, temperature_threshold=temperature_threshold
    )


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
