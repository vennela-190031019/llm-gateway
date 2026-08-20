"""Provider-agnostic chat completion request/response envelope.

`ChatCompletionRequest` is what every `LLMProvider.complete()` accepts;
`ChatCompletionResponse` is the common shape every provider normalizes
its raw backend response into, regardless of vendor.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ChatRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    TOOL_CALLS = "tool_calls"


class ChatRequestMetadata(BaseModel):
    """Request-level flags that don't affect the completion output itself.

    Kept out of the cache key on purpose — see app.services.cache.
    """

    cacheable: bool = True


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = 1.0
    max_tokens: int | None = None
    metadata: ChatRequestMetadata = Field(default_factory=ChatRequestMetadata)


class ChatCompletionResponse(BaseModel):
    provider: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    finish_reason: FinishReason
    latency_ms: float
    cached: bool = False


class ChatCompletionChunk(BaseModel):
    """A single streaming delta. Not produced by any provider yet."""

    provider: str
    model: str
    delta: str
    finish_reason: FinishReason | None = None
