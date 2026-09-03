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
    # 50k chars is generous for a single message while still bounding
    # per-message abuse; the overall body-size limit (see
    # app.core.middleware) is the backstop for the request as a whole.
    content: str = Field(max_length=50_000)


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
    task_type: str | None = Field(default=None, max_length=100)


class ChatCompletionRequest(BaseModel):
    model: str = Field(max_length=200)
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=1.0, ge=0, le=2)
    # No provider actually supports 32k+ output tokens today, but this is
    # a schema-level sanity ceiling, not a model-specific one — providers
    # still reject values their own model can't honor.
    max_tokens: int | None = Field(default=None, gt=0, le=32_000)
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
