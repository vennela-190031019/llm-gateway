from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.config import get_settings
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.registry import UnknownProviderError, get_provider


@pytest.fixture(autouse=True)
def _fresh_provider_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # AsyncOpenAI validates credentials at construction time (no network
    # call involved) — give it a fake key so building an OpenAIProvider
    # here doesn't depend on the real (possibly unset) OPENAI_API_KEY.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    get_provider.cache_clear()
    yield
    get_provider.cache_clear()
    get_settings.cache_clear()


def test_get_provider_returns_openai_provider() -> None:
    assert isinstance(get_provider("openai"), OpenAIProvider)


def test_get_provider_returns_ollama_provider() -> None:
    assert isinstance(get_provider("ollama"), OllamaProvider)


def test_get_provider_caches_instances_per_name() -> None:
    assert get_provider("openai") is get_provider("openai")


def test_get_provider_raises_for_unknown_name() -> None:
    with pytest.raises(UnknownProviderError):
        get_provider("does-not-exist")
