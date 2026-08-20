"""Redis-backed cache for deterministic chat completions.

Only requests that are actually deterministic are cached: low enough
temperature (below settings.cache_temperature_threshold) and not marked
`cacheable=False` (e.g. because the request contains sensitive data).
The cache key is a hash of exactly the fields that affect the model's
output — request-level flags like `metadata` are deliberately excluded.

Caching is a resilience-neutral optimization, not a hard dependency: if
Redis is unreachable, every method logs a warning and behaves as a
cache miss / no-op instead of raising, so the caller always falls
through to calling the provider directly.
"""

from __future__ import annotations

import hashlib
import json

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import llm_cache_hits_total, llm_cache_misses_total
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse

logger = get_logger(__name__)

KEY_PREFIX = "llm-gateway:chat-cache:"


def cache_key(request: ChatCompletionRequest) -> str:
    """Deterministic key over exactly the fields that affect the output."""
    payload = {
        "model": request.model,
        "messages": [message.model_dump(mode="json") for message in request.messages],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{KEY_PREFIX}{digest}"


class CacheService:
    def __init__(
        self,
        client: redis.Redis | None = None,
        *,
        ttl_seconds: int | None = None,
        temperature_threshold: float | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client or redis.from_url(settings.redis_url, decode_responses=True)
        self._ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.cache_ttl_seconds
        self._temperature_threshold = (
            temperature_threshold
            if temperature_threshold is not None
            else settings.cache_temperature_threshold
        )

    def is_cacheable(self, request: ChatCompletionRequest) -> bool:
        return (
            request.metadata.cacheable
            and request.temperature <= self._temperature_threshold
        )

    async def get(self, request: ChatCompletionRequest) -> ChatCompletionResponse | None:
        if not self.is_cacheable(request):
            return None

        key = cache_key(request)
        try:
            raw = await self._client.get(key)
        except redis.RedisError as exc:
            logger.warning("cache_get_failed", error=str(exc))
            return None

        if raw is None:
            llm_cache_misses_total.inc()
            return None

        llm_cache_hits_total.inc()
        response = ChatCompletionResponse.model_validate_json(raw)
        return response.model_copy(update={"cached": True})

    async def set(self, request: ChatCompletionRequest, response: ChatCompletionResponse) -> None:
        if not self.is_cacheable(request):
            return

        key = cache_key(request)
        payload = response.model_copy(update={"cached": False}).model_dump_json()
        try:
            await self._client.set(key, payload, ex=self._ttl_seconds)
        except redis.RedisError as exc:
            logger.warning("cache_set_failed", error=str(exc))

    async def invalidate(self, request: ChatCompletionRequest) -> None:
        """Clear the cached entry for this specific request, if any."""
        key = cache_key(request)
        try:
            await self._client.delete(key)
        except redis.RedisError as exc:
            logger.warning("cache_invalidate_failed", error=str(exc))

    async def flush(self) -> None:
        """Clear every cached completion (our key namespace only)."""
        try:
            keys = [key async for key in self._client.scan_iter(match=f"{KEY_PREFIX}*")]
            if keys:
                await self._client.delete(*keys)
        except redis.RedisError as exc:
            logger.warning("cache_flush_failed", error=str(exc))
