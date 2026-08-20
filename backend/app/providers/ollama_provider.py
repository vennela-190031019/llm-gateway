"""Ollama provider — talks to a local Ollama instance over its native REST API."""

from __future__ import annotations

import time
from typing import Any

import httpx

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

_DONE_REASON_MAP = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
}
_DEFAULT_TIMEOUT_SECONDS = 60.0


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._client = client or httpx.AsyncClient(
            base_url=settings.ollama_base_url, timeout=_DEFAULT_TIMEOUT_SECONDS
        )

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        started = time.monotonic()
        options: dict[str, Any] = {"temperature": request.temperature}
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "stream": False,
            "options": options,
        }

        try:
            http_response = await self._client.post("/api/chat", json=payload)
            http_response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(self.name, str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_status_error(exc) from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(self.name, str(exc)) from exc
        latency_ms = (time.monotonic() - started) * 1000

        try:
            body = http_response.json()
            content = body["message"]["content"]
            input_tokens = body["prompt_eval_count"]
            output_tokens = body["eval_count"]
            model = body["model"]
            finish_reason = _DONE_REASON_MAP.get(body.get("done_reason", ""), FinishReason.STOP)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(self.name, f"malformed response: {exc}") from exc

        return ChatCompletionResponse(
            provider=self.name,
            model=model,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
        )

    def _map_status_error(self, exc: httpx.HTTPStatusError) -> ProviderError:
        status_code = exc.response.status_code
        if status_code == 429:
            return ProviderRateLimitError(self.name, str(exc))
        if status_code in (401, 403):
            return ProviderAuthenticationError(self.name, str(exc))
        return ProviderError(self.name, str(exc))
