"""Abstract interface all LLM providers implement.

Concrete providers normalize whatever shape their backend returns into
the common `ChatCompletionResponse`, so callers never branch on which
provider they're talking to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas.chat import ChatCompletionChunk, ChatCompletionRequest, ChatCompletionResponse


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Send a single request and return the full completion."""
        raise NotImplementedError

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]:
        """Token-streaming variant of `complete`.

        Not implemented by any provider in this phase — see Phase 4
        (routing + fallback), which is expected to add streaming support.
        Providers can override this once they support it.
        """
        raise NotImplementedError(f"{self.name} provider does not support streaming yet")
        yield  # pragma: no cover - keeps this an async generator for typing
