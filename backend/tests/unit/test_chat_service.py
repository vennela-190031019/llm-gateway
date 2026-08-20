"""Integration-style tests for ChatCompletionService using the real
ModelRouter (backed by app/core/routing_rules.yaml) and FallbackExecutor,
with the provider registry monkeypatched to fake providers.
"""

from __future__ import annotations

import pytest
from tenacity import wait_none

from app.providers.exceptions import ProviderTimeoutError
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatRole
from app.services import fallback as fallback_module
from app.services.chat_service import ChatCompletionService
from app.services.fallback import AllProvidersExhaustedError, FallbackExecutor
from app.services.router import ModelRouter

from .fakes import FakeProvider, make_response


def _request(model: str) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model, messages=[ChatMessage(role=ChatRole.USER, content="hi")]
    )


def _service() -> ChatCompletionService:
    return ChatCompletionService(router=ModelRouter(), executor=FallbackExecutor(wait=wait_none()))


def _patch_providers(monkeypatch: pytest.MonkeyPatch, providers: dict[str, FakeProvider]) -> None:
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: providers[name])


async def test_complete_returns_first_successful_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_provider = FakeProvider(
        "openai", [make_response(provider="openai", model="gpt-4o-mini")]
    )
    _patch_providers(monkeypatch, {"openai": openai_provider})

    result = await _service().complete(_request("gpt-4o-mini"), task_type="summarization")

    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"


async def test_complete_falls_back_to_ollama_when_openai_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_provider = FakeProvider("openai", [ProviderTimeoutError("openai", "slow")] * 3)
    ollama_provider = FakeProvider("ollama", [make_response(provider="ollama", model="llama3.1")])
    _patch_providers(monkeypatch, {"openai": openai_provider, "ollama": ollama_provider})

    result = await _service().complete(_request("gpt-4o-mini"), task_type="summarization")

    assert result.provider == "ollama"
    assert result.model == "llama3.1"
    assert openai_provider.calls == 3


async def test_complete_uses_default_rule_when_task_type_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_provider = FakeProvider("openai", [make_response(provider="openai", model="gpt-4o")])
    _patch_providers(monkeypatch, {"openai": openai_provider})

    result = await _service().complete(_request("gpt-4o"))

    assert result.provider == "openai"


async def test_complete_raises_all_providers_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    openai_provider = FakeProvider("openai", [ProviderTimeoutError("openai", "slow")] * 3)
    ollama_provider = FakeProvider("ollama", [ProviderTimeoutError("ollama", "slow")] * 3)
    _patch_providers(monkeypatch, {"openai": openai_provider, "ollama": ollama_provider})

    with pytest.raises(AllProvidersExhaustedError):
        await _service().complete(_request("gpt-4o-mini"), task_type="summarization")
