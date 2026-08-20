"""Top-level chat completion orchestration: routing + retry + fallback.

Not wired into the /chat HTTP endpoint yet — that happens in a later
phase, once caching and cost tracking are layered on top too.
"""

from __future__ import annotations

from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from app.services.fallback import AllProvidersExhaustedError, FallbackExecutor
from app.services.router import ModelRouter


class ChatCompletionService:
    def __init__(
        self,
        router: ModelRouter | None = None,
        executor: FallbackExecutor | None = None,
    ) -> None:
        self._router = router or ModelRouter()
        self._executor = executor or FallbackExecutor()

    async def complete(
        self, request: ChatCompletionRequest, task_type: str | None = None
    ) -> ChatCompletionResponse:
        """Resolve candidates for `request.model` and try them in order.

        Returns the first successful response, or raises
        AllProvidersExhaustedError if every candidate fails.
        """
        candidates = self._router.get_candidates(request.model, task_type)
        return await self._executor.run(candidates, request)


__all__ = ["AllProvidersExhaustedError", "ChatCompletionService"]
