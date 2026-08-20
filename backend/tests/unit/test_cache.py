from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis as fakeredis
from prometheus_client import Counter
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.metrics import llm_cache_hits_total, llm_cache_misses_total
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatRequestMetadata, ChatRole
from app.services.cache import KEY_PREFIX, CacheService, cache_key

from .fakes import make_fake_cache_service, make_response


class _DownRedis:
    """Stands in for a Redis client whose connection is unreachable."""

    async def get(self, key: str) -> str | None:
        raise RedisConnectionError("connection refused")

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise RedisConnectionError("connection refused")

    async def delete(self, *keys: str) -> None:
        raise RedisConnectionError("connection refused")

    def scan_iter(self, match: str | None = None) -> AsyncIterator[str]:
        raise RedisConnectionError("connection refused")


def _request(
    *,
    model: str = "gpt-4o-mini",
    content: str = "hi",
    temperature: float = 0.0,
    max_tokens: int | None = None,
    cacheable: bool = True,
) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[ChatMessage(role=ChatRole.USER, content=content)],
        temperature=temperature,
        max_tokens=max_tokens,
        metadata=ChatRequestMetadata(cacheable=cacheable),
    )


def _counter_value(counter: Counter) -> float:
    return float(counter._value.get())


async def test_get_misses_when_nothing_cached() -> None:
    service = make_fake_cache_service()

    result = await service.get(_request())

    assert result is None


async def test_set_then_get_is_a_cache_hit_on_identical_request() -> None:
    service = make_fake_cache_service()
    request = _request()
    response = make_response(provider="openai", model="gpt-4o-mini", content="hello there")

    await service.set(request, response)
    cached = await service.get(request)

    assert cached is not None
    assert cached.content == "hello there"
    assert cached.cached is True


async def test_cached_response_is_stored_with_cached_false() -> None:
    """The flag is set on read, not baked into the stored payload."""
    service = make_fake_cache_service()
    request = _request()
    response = make_response(provider="openai", model="gpt-4o-mini")
    assert response.cached is False

    await service.set(request, response)
    first_read = await service.get(request)
    second_read = await service.get(request)

    assert first_read is not None and first_read.cached is True
    assert second_read is not None and second_read.cached is True


async def test_different_requests_produce_different_cache_keys() -> None:
    key_a = cache_key(_request(content="hello"))
    key_b = cache_key(_request(content="goodbye"))
    key_c = cache_key(_request(model="gpt-4o"))
    key_d = cache_key(_request(max_tokens=128))

    assert len({key_a, key_b, key_c, key_d}) == 4
    assert all(key.startswith(KEY_PREFIX) for key in (key_a, key_b, key_c, key_d))


async def test_metadata_does_not_affect_cache_key() -> None:
    cacheable_key = cache_key(_request(cacheable=True))
    non_cacheable_key = cache_key(_request(cacheable=False))

    assert cacheable_key == non_cacheable_key


async def test_high_temperature_requests_skip_caching() -> None:
    service = make_fake_cache_service(temperature_threshold=0.2)
    request = _request(temperature=0.9)
    response = make_response(provider="openai", model="gpt-4o-mini")

    await service.set(request, response)
    cached = await service.get(request)

    assert cached is None


async def test_temperature_at_threshold_is_still_cacheable() -> None:
    service = make_fake_cache_service(temperature_threshold=0.2)
    request = _request(temperature=0.2)
    response = make_response(provider="openai", model="gpt-4o-mini")

    await service.set(request, response)
    cached = await service.get(request)

    assert cached is not None


async def test_cacheable_false_skips_caching() -> None:
    service = make_fake_cache_service()
    request = _request(cacheable=False)
    response = make_response(provider="openai", model="gpt-4o-mini")

    await service.set(request, response)
    cached = await service.get(request)

    assert cached is None


async def test_ttl_is_set_on_write() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    service = CacheService(client=client, ttl_seconds=123, temperature_threshold=0.0)
    request = _request()
    response = make_response(provider="openai", model="gpt-4o-mini")

    await service.set(request, response)

    ttl = await client.ttl(cache_key(request))
    assert 0 < ttl <= 123


async def test_invalidate_removes_specific_entry() -> None:
    service = make_fake_cache_service()
    request = _request()
    response = make_response(provider="openai", model="gpt-4o-mini")
    await service.set(request, response)

    await service.invalidate(request)

    assert await service.get(request) is None


async def test_flush_clears_every_cached_entry() -> None:
    service = make_fake_cache_service()
    first = _request(content="one")
    second = _request(content="two")
    await service.set(first, make_response(provider="openai", model="gpt-4o-mini"))
    await service.set(second, make_response(provider="openai", model="gpt-4o-mini"))

    await service.flush()

    assert await service.get(first) is None
    assert await service.get(second) is None


async def test_flush_does_not_touch_keys_outside_our_namespace() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    await client.set("some-unrelated-key", "keep-me")
    service = CacheService(client=client, ttl_seconds=60, temperature_threshold=0.0)
    await service.set(_request(), make_response(provider="openai", model="gpt-4o-mini"))

    await service.flush()

    assert await client.get("some-unrelated-key") == "keep-me"


async def test_get_falls_through_when_redis_is_down() -> None:
    service = CacheService(client=_DownRedis(), ttl_seconds=60, temperature_threshold=0.0)

    result = await service.get(_request())

    assert result is None


async def test_set_falls_through_when_redis_is_down() -> None:
    service = CacheService(client=_DownRedis(), ttl_seconds=60, temperature_threshold=0.0)

    # Must not raise.
    await service.set(_request(), make_response(provider="openai", model="gpt-4o-mini"))


async def test_flush_falls_through_when_redis_is_down() -> None:
    service = CacheService(client=_DownRedis(), ttl_seconds=60, temperature_threshold=0.0)

    # Must not raise.
    await service.flush()


async def test_invalidate_falls_through_when_redis_is_down() -> None:
    service = CacheService(client=_DownRedis(), ttl_seconds=60, temperature_threshold=0.0)

    # Must not raise.
    await service.invalidate(_request())


async def test_hit_and_miss_metrics_increment() -> None:
    service = make_fake_cache_service()
    request = _request()
    misses_before = _counter_value(llm_cache_misses_total)
    hits_before = _counter_value(llm_cache_hits_total)

    await service.get(request)  # miss
    await service.set(request, make_response(provider="openai", model="gpt-4o-mini"))
    await service.get(request)  # hit
    await service.get(request)  # hit

    assert _counter_value(llm_cache_misses_total) == misses_before + 1
    assert _counter_value(llm_cache_hits_total) == hits_before + 2


async def test_uncacheable_request_does_not_move_metrics() -> None:
    service = make_fake_cache_service()
    request = _request(cacheable=False)
    misses_before = _counter_value(llm_cache_misses_total)
    hits_before = _counter_value(llm_cache_hits_total)

    await service.get(request)

    assert _counter_value(llm_cache_misses_total) == misses_before
    assert _counter_value(llm_cache_hits_total) == hits_before
