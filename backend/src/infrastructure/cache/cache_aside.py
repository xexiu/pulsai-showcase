"""Generic fail-open cache-aside helper for JSON-serializable values.

Read-through Redis caching: return the cached value on hit, otherwise call the
``loader``, store its (JSON-serializable) result with a TTL, and return it.

Every Redis interaction is **fail-open** — a Redis outage (connect/read/write)
degrades to a direct ``loader`` call and never raises, so callers keep working
and only lose the cache benefit. Fail-open is scoped to ``REDIS_FAULTS``
(``RedisError`` + ``OSError``, the SoT tuple in ``redis_best_effort``), NOT to
``Exception``: a ``TypeError`` or ``AttributeError`` here is a bug in our own
code, and swallowing it turned a broken cache into a permanent silent miss that
looked exactly like a cold one. Mirrors the read-through, fail-open contract of
:class:`~src.infrastructure.cache.market_limits_cache.MarketLimitsRedisCache`
but stays value-agnostic so any caller can cache a dict/list payload.

``cache_aside_json_batch`` is the multi-key form: probe all keys, load misses in
bounded chunks (one loader call per chunk), write each non-empty result back.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeVar

from src.infrastructure.cache.redis_best_effort import REDIS_FAULTS
from src.infrastructure.cache.redis_client import get_redis_client

logger = logging.getLogger(__name__)

JsonValue = dict[str, Any] | list[Any]
T = TypeVar("T")

#: Default miss-loader chunk size — bounds RSS/GPU for heavy loaders (e.g. FinBERT).
CACHE_ASIDE_BATCH_CHUNK_SIZE: int = 32


class RedisJsonCache(Protocol):
    """Minimal structural surface this helper needs from a Redis client (DIP/ISP).

    The shared ``RedisClient`` satisfies it; tests can inject any double with the
    same two methods without depending on the concrete client.
    """

    async def get_json(self, key: str) -> JsonValue | None: ...

    async def set_json(self, key: str, value: JsonValue, ex: int | None = None) -> bool: ...


async def cache_aside_json(
    *,
    key: str,
    ttl_seconds: int,
    loader: Callable[[], Awaitable[JsonValue]],
    redis_client: RedisJsonCache | None = None,
) -> JsonValue:
    """Return ``key`` from Redis, or compute it via ``loader`` and cache it.

    Args:
        key: cache key (SoT builders live on :class:`CacheKeys`).
        ttl_seconds: expiry applied to the stored value.
        loader: async callable producing a JSON-serializable value on a miss.
        redis_client: optional injected client (tests); defaults to the shared
            singleton via :func:`get_redis_client`.

    Returns:
        The cached value on hit, else the loader's result. Fail-open: any Redis
        error falls back to the loader, is logged, and is never raised.

    An empty result (``[]`` / ``{}``) is returned to the caller but NOT cached:
    a transient upstream outage that yields nothing would otherwise be served
    stale for the full TTL. Skipping the write makes the next call retry.
    """
    redis = redis_client if redis_client is not None else await _try_get_client()

    if redis is not None:
        cached = await _try_read(redis, key)
        if cached is not None:
            return cached

    value = await loader()

    # Skip negative caching: don't persist an empty payload (see docstring).
    if redis is not None and value:
        await _try_write(redis, key, value, ttl_seconds)

    return value


async def cache_aside_json_batch[T](
    items: Sequence[T],
    *,
    key_for: Callable[[T], str],
    ttl_seconds: int,
    load_misses: Callable[[Sequence[T]], Awaitable[Sequence[JsonValue]]],
    redis_client: RedisJsonCache | None = None,
    chunk_size: int | None = None,
    normalize_hit: Callable[[JsonValue], JsonValue | None] | None = None,
    ttl_for: Callable[[JsonValue], int] | None = None,
) -> list[JsonValue]:
    """Cache-aside for many items: hits from Redis, misses loaded in chunks.

    Args:
        items: values to resolve (order preserved in the return list).
        key_for: maps each item to its Redis key.
        ttl_seconds: default expiry for newly written values.
        load_misses: async loader for one miss chunk; must return values aligned
            1:1 with the chunk (short returns are padded with ``{}``).
        redis_client: optional injected client; ``None`` resolves the shared
            singleton (fail-open → all items treated as misses).
        chunk_size: max misses per ``load_misses`` call. ``None`` uses
            :data:`CACHE_ASIDE_BATCH_CHUNK_SIZE` at call time (monkeypatch-friendly).
        normalize_hit: optional hit filter — return ``None`` to treat a cached
            payload as a miss (e.g. malformed Phase-2 verdicts).
        ttl_for: optional per-value TTL (e.g. shorter TTL for directional LLM
            verdicts). Falls back to ``ttl_seconds`` when omitted.

    Returns:
        One JSON value per input item. Empty loader payloads are returned but not
        written (same negative-caching rule as :func:`cache_aside_json`).
    """
    if not items:
        return []

    size = CACHE_ASIDE_BATCH_CHUNK_SIZE if chunk_size is None else chunk_size
    if size < 1:
        raise ValueError(f"chunk_size must be >= 1, got {size}")

    redis = redis_client if redis_client is not None else await _try_get_client()
    results: list[JsonValue | None] = [None] * len(items)
    miss_indices: list[int] = []

    cached_values = await _probe_all(redis, items, key_for=key_for, window=size)

    for index in range(len(items)):
        if redis is None:
            miss_indices.append(index)
            continue
        cached = cached_values[index]
        if cached is not None and cached:
            accepted = normalize_hit(cached) if normalize_hit is not None else cached
            if accepted is not None:
                results[index] = accepted
                continue
        # Missing key, Redis error, empty/rejected payload → recompute.
        miss_indices.append(index)

    for start in range(0, len(miss_indices), size):
        chunk_indices = miss_indices[start : start + size]
        chunk_items = [items[i] for i in chunk_indices]
        loaded = list(await load_misses(chunk_items))
        while len(loaded) < len(chunk_items):
            loaded.append({})
        for offset, index in enumerate(chunk_indices):
            value = loaded[offset]
            results[index] = value
            if redis is not None and value:
                write_ttl = ttl_for(value) if ttl_for is not None else ttl_seconds
                await _try_write(redis, key_for(items[index]), value, write_ttl)

    return [row if row is not None else {} for row in results]


async def _probe_all[T](
    redis: RedisJsonCache | None,
    items: Sequence[T],
    *,
    key_for: Callable[[T], str],
    window: int,
) -> list[JsonValue | None]:
    """Read every item's key CONCURRENTLY, aligned 1:1 with ``items``.

    This was a `for` loop awaiting once per item, so resolving N items cost N STACKED round
    trips before any loader ran -- a function named `_batch` paying the sequential price it
    exists to avoid. Found by an AST sweep for `await` assigned inside a `for` loop; the same
    defect, and the same giveaway name, as the OHLCV heartbeat read fixed the same night.

    GATHERED RATHER THAN MGET, deliberately. :class:`RedisJsonCache` is a minimal Protocol --
    ``get_json`` and ``set_json``, so "tests can inject any double with the same two methods".
    Adding ``mget_json`` would force every implementer to grow a method to serve one caller,
    which is the ISP violation that Protocol is shaped to avoid. Gathering collapses the latency
    from N x RTT to about one, and leaves the interface, every double and all nine sibling tests
    untouched.

    Bounded by ``window`` -- the same chunk size the miss loader uses -- because an unbounded
    fan-out would hand the connection pool an arbitrary burst, and that constant is already this
    module's answer to "how much at once". :func:`_try_read` is fail-open, so one bad key cannot
    take its siblings down with it.

    Returns all ``None`` when there is no client, which the caller reads as all-misses.
    """
    if redis is None:
        return [None] * len(items)

    probed: list[JsonValue | None] = []
    for start in range(0, len(items), window):
        chunk = items[start : start + window]
        probed.extend(await asyncio.gather(*(_try_read(redis, key_for(item)) for item in chunk)))
    return probed


async def _try_get_client() -> RedisJsonCache | None:
    """Resolve the shared Redis client, or ``None`` if it is unavailable (fail-open)."""
    try:
        return await get_redis_client()
    except REDIS_FAULTS as exc:
        logger.warning("cache_aside: redis unavailable, bypassing cache: %s", exc)
        return None


async def _try_read(redis: RedisJsonCache, key: str) -> JsonValue | None:
    """Read+decode ``key``, returning ``None`` on miss or any Redis error (fail-open)."""
    try:
        return await redis.get_json(key)
    except REDIS_FAULTS as exc:
        logger.warning("cache_aside: read failed for %s, falling back to loader: %s", key, exc)
        return None


async def _try_write(redis: RedisJsonCache, key: str, value: JsonValue, ttl_seconds: int) -> None:
    """Best-effort write of ``value`` under ``key``; swallow Redis errors (fail-open)."""
    try:
        await redis.set_json(key, value, ex=ttl_seconds)
    except REDIS_FAULTS as exc:
        logger.warning("cache_aside: write failed for %s (will recompute next miss): %s", key, exc)
