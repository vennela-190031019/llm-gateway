"""Top-level chat completion orchestration: cache + routing + retry + fallback.

Not wired into the /chat HTTP endpoint yet — that happens in a later
phase, once cost tracking is layered on top too.
"""

from __future__ import annotations

from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from app.services.cache import CacheService
from app.services.fallback import AllProvidersExhaustedError, FallbackExecutor
from app.services.router import ModelRouter


class ChatCompletionService:
    def __init__(
        self,
        router: ModelRouter | None = None,
        executor: FallbackExecutor | None = None,
        cache: CacheService | None = None,
    ) -> None:
        self._router = router or ModelRouter()
        self._executor = executor or FallbackExecutor()
        self._cache = cache or CacheService()

    async def complete(
        self, request: ChatCompletionRequest, task_type: str | None = None
    ) -> ChatCompletionResponse:
        """Resolve candidates for `request.model` and try them in order.

        Checks the cache first and returns a cached response immediately
        on a hit. On a miss, runs the normal routing/retry/fallback flow
        and caches the result (if the request is cacheable) before
        returning it.

        Raises AllProvidersExhaustedError if every candidate fails.
        """
        cached = await self._cache.get(request)
        if cached is not None:
            return cached

        candidates = self._router.get_candidates(request.model, task_type)
        response = await self._executor.run(candidates, request)
        await self._cache.set(request, response)
        return response


__all__ = ["AllProvidersExhaustedError", "ChatCompletionService"]
