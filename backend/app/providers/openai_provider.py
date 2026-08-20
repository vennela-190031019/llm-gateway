"""OpenAI provider — talks to the OpenAI Chat Completions API."""

from __future__ import annotations

import time
from typing import cast

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import get_settings
from app.providers.base import LLMProvider
from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse, FinishReason

_FINISH_REASON_MAP = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
    "tool_calls": FinishReason.TOOL_CALLS,
    "function_call": FinishReason.TOOL_CALLS,
}


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()
        self._client = client or AsyncOpenAI(
            api_key=settings.openai_api_key, base_url=settings.openai_base_url
        )

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        started = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=request.model,
                messages=cast(
                    list[ChatCompletionMessageParam],
                    [
                        {"role": message.role.value, "content": message.content}
                        for message in request.messages
                    ],
                ),
                temperature=request.temperature,
                max_tokens=(
                    request.max_tokens if request.max_tokens is not None else openai.omit
                ),
            )
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(self.name, str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise ProviderUnavailableError(self.name, str(exc)) from exc
        except openai.RateLimitError as exc:
            raise ProviderRateLimitError(self.name, str(exc)) from exc
        except openai.AuthenticationError as exc:
            raise ProviderAuthenticationError(self.name, str(exc)) from exc
        except openai.APIStatusError as exc:
            raise ProviderError(self.name, str(exc)) from exc
        latency_ms = (time.monotonic() - started) * 1000

        try:
            choice = response.choices[0]
            content = choice.message.content
            if content is None:
                raise ValueError("choice message content is null")
            usage = response.usage
            if usage is None:
                raise ValueError("response is missing usage data")
            finish_reason = _FINISH_REASON_MAP.get(choice.finish_reason, FinishReason.STOP)
        except (IndexError, AttributeError, ValueError) as exc:
            raise ProviderResponseError(self.name, f"malformed response: {exc}") from exc

        return ChatCompletionResponse(
            provider=self.name,
            model=response.model,
            content=content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
        )
