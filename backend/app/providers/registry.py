"""Maps a provider name to a provider instance.

Callers (e.g. the future routing service) ask for a provider by name —
the same string stored on `Provider.name` in the DB — without needing to
import or know about any concrete provider class.
"""

from __future__ import annotations

from functools import lru_cache

from app.providers.base import LLMProvider
from app.providers.exceptions import ProviderError
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider


class UnknownProviderError(ProviderError):
    """Raised when asked to build a provider that isn't registered."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "no provider registered under this name")


_PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    OpenAIProvider.name: OpenAIProvider,
    OllamaProvider.name: OllamaProvider,
}


@lru_cache
def get_provider(name: str) -> LLMProvider:
    """Return a cached provider instance for `name`.

    Instances are cached (keyed by name) so the underlying HTTP client
    each provider owns is reused rather than reconnected per call.
    """
    try:
        provider_cls = _PROVIDER_CLASSES[name]
    except KeyError:
        raise UnknownProviderError(name) from None
    return provider_cls()
