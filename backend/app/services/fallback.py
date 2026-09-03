"""Retry-with-backoff + fallback execution over an ordered candidate list.

Given an ordered list of (provider_name, model_name) candidates, tries
each in turn: transient provider errors (timeout, unavailable, rate
limit) are retried with exponential backoff, capped at a few attempts,
before moving to the next candidate. Non-transient errors (bad
credentials, malformed response) are not retried — they fail straight
to the next candidate. If every candidate fails, raises
AllProvidersExhaustedError with the reason each one failed.
"""

from __future__ import annotations

from dataclasses import dataclass

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from tenacity.wait import WaitBaseT

from app.core.metrics import llm_errors_total
from app.providers.exceptions import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.registry import get_provider
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse

MAX_ATTEMPTS_PER_CANDIDATE = 3
TRANSIENT_ERRORS: tuple[type[ProviderError], ...] = (
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderRateLimitError,
)


@dataclass(frozen=True)
class CandidateFailure:
    provider: str
    model: str
    error: str


class AllProvidersExhaustedError(Exception):
    """Raised when every routing candidate failed."""

    def __init__(self, failures: list[CandidateFailure]) -> None:
        self.failures = failures
        summary = "; ".join(f"{f.provider}/{f.model}: {f.error}" for f in failures)
        super().__init__(f"all providers exhausted: {summary}")


class FallbackExecutor:
    def __init__(
        self,
        *,
        max_attempts_per_candidate: int = MAX_ATTEMPTS_PER_CANDIDATE,
        wait: WaitBaseT | None = None,
    ) -> None:
        self._max_attempts = max_attempts_per_candidate
        self._wait = wait if wait is not None else wait_exponential(multiplier=0.5, max=10)

    async def run(
        self, candidates: list[tuple[str, str]], request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        failures: list[CandidateFailure] = []

        for provider_name, model_name in candidates:
            candidate_request = request.model_copy(update={"model": model_name})
            retrying = AsyncRetrying(
                reraise=True,
                stop=stop_after_attempt(self._max_attempts),
                wait=self._wait,
                retry=retry_if_exception_type(TRANSIENT_ERRORS),
            )
            try:
                # get_provider() is inside this try deliberately: building a
                # provider can fail too (e.g. ProviderConfigurationError for
                # a missing API key), and that must be treated as a
                # candidate failure — eligible for fallback to the next
                # candidate — the same as a failure from .complete() itself,
                # not left to propagate as an unhandled 500.
                provider = get_provider(provider_name)
                return await retrying(provider.complete, candidate_request)
            except ProviderError as exc:
                failures.append(CandidateFailure(provider_name, model_name, str(exc)))
                # Recorded per-candidate (not just on total exhaustion) so
                # "errors by provider" stays meaningful even when a later
                # candidate saves the request — otherwise a provider that
                # fails on every request but always loses the race to
                # fallback would never show up in llm_errors_total at all.
                llm_errors_total.labels(
                    model=model_name, provider=provider_name, error_type=type(exc).__name__
                ).inc()

        raise AllProvidersExhaustedError(failures)
