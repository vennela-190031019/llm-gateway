from __future__ import annotations

import pytest
from tenacity import wait_none

from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatRole
from app.services import fallback as fallback_module
from app.services.fallback import AllProvidersExhaustedError, FallbackExecutor

from .fakes import FakeProvider, make_response


def _request() -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="gpt-4o", messages=[ChatMessage(role=ChatRole.USER, content="hi")]
    )


def _executor() -> FallbackExecutor:
    return FallbackExecutor(wait=wait_none())


def _patch_providers(monkeypatch: pytest.MonkeyPatch, providers: dict[str, FakeProvider]) -> None:
    monkeypatch.setattr(fallback_module, "get_provider", lambda name: providers[name])


async def test_run_succeeds_on_first_try(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeProvider("openai", [make_response(provider="openai", model="gpt-4o")])
    _patch_providers(monkeypatch, {"openai": provider})

    result = await _executor().run([("openai", "gpt-4o")], _request())

    assert result.provider == "openai"
    assert provider.calls == 1


async def test_run_retries_transient_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider(
        "openai",
        [
            ProviderTimeoutError("openai", "slow"),
            ProviderUnavailableError("openai", "down"),
            make_response(provider="openai", model="gpt-4o"),
        ],
    )
    _patch_providers(monkeypatch, {"openai": provider})

    result = await _executor().run([("openai", "gpt-4o")], _request())

    assert result.provider == "openai"
    assert provider.calls == 3


async def test_run_falls_back_to_next_candidate_after_retries_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_provider = FakeProvider("openai", [ProviderTimeoutError("openai", "slow")] * 3)
    ollama_provider = FakeProvider("ollama", [make_response(provider="ollama", model="llama3.1")])
    _patch_providers(monkeypatch, {"openai": openai_provider, "ollama": ollama_provider})

    result = await _executor().run([("openai", "gpt-4o"), ("ollama", "llama3.1")], _request())

    assert result.provider == "ollama"
    assert openai_provider.calls == 3
    assert ollama_provider.calls == 1


async def test_run_raises_all_providers_exhausted_when_every_candidate_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_provider = FakeProvider("openai", [ProviderTimeoutError("openai", "slow")] * 3)
    ollama_provider = FakeProvider("ollama", [ProviderUnavailableError("ollama", "down")] * 3)
    _patch_providers(monkeypatch, {"openai": openai_provider, "ollama": ollama_provider})

    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await _executor().run([("openai", "gpt-4o"), ("ollama", "llama3.1")], _request())

    failures = exc_info.value.failures
    assert [f.provider for f in failures] == ["openai", "ollama"]
    assert [f.model for f in failures] == ["gpt-4o", "llama3.1"]
    assert openai_provider.calls == 3
    assert ollama_provider.calls == 3


async def test_run_skips_retry_for_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    openai_provider = FakeProvider("openai", [ProviderAuthenticationError("openai", "bad key")])
    ollama_provider = FakeProvider("ollama", [make_response(provider="ollama", model="llama3.1")])
    _patch_providers(monkeypatch, {"openai": openai_provider, "ollama": ollama_provider})

    result = await _executor().run([("openai", "gpt-4o"), ("ollama", "llama3.1")], _request())

    assert result.provider == "ollama"
    assert openai_provider.calls == 1
    assert ollama_provider.calls == 1


async def test_run_skips_retry_for_malformed_response_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openai_provider = FakeProvider("openai", [ProviderResponseError("openai", "bad json")])
    ollama_provider = FakeProvider("ollama", [make_response(provider="ollama", model="llama3.1")])
    _patch_providers(monkeypatch, {"openai": openai_provider, "ollama": ollama_provider})

    result = await _executor().run([("openai", "gpt-4o"), ("ollama", "llama3.1")], _request())

    assert result.provider == "ollama"
    assert openai_provider.calls == 1
