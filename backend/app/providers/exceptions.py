"""Typed exceptions for the provider layer.

Raw SDK/httpx exceptions never leave `app.providers` — every provider
catches its backend's exceptions and re-raises one of these, so callers
have a single, provider-agnostic error contract to handle.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all provider-layer errors."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""


class ProviderUnavailableError(ProviderError):
    """The provider could not be reached (connection refused, DNS, etc.)."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request due to rate limiting."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected our credentials."""


class ProviderConfigurationError(ProviderError):
    """The provider couldn't even be constructed (e.g. missing API key) —
    a local misconfiguration, not something the provider itself rejected.
    Never worth retrying.
    """


class ProviderResponseError(ProviderError):
    """The provider responded, but with a malformed or unexpected payload."""
