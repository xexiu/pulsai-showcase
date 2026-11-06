"""Best-effort Redis client acquisition for optional cache short-circuits."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

if TYPE_CHECKING:
    from src.infrastructure.cache.redis_client import RedisClient

logger = logging.getLogger(__name__)

#: What a Redis call can ACTUALLY fail with. SoT for the best-effort cache paths, so the tuple is
#: named once rather than re-typed at each `except`.
#:
#: redis-py raises `RedisError` subclasses for protocol and connection faults; the transport under
#: it raises `OSError`, and Python's builtin `ConnectionError` is an `OSError` subclass -- which is
#: what the cache tests inject. Fail-open is preserved for every fault a cache can really have;
#: what these no longer swallow is a TypeError or AttributeError, which is a bug in our own code
#: rather than Redis being down.
REDIS_FAULTS: tuple[type[BaseException], ...] = (RedisError, OSError)

#: What a JSON snapshot cache WRITE can fail with: Redis itself, or ``orjson.JSONEncodeError`` (a
#: TypeError) on an unserializable payload. One home for the derivatives-flow and taker-flow writes,
#: which each caught bare ``Exception`` around the same SET (2026-10-03).
REDIS_CACHE_WRITE_FAULTS: tuple[type[BaseException], ...] = (*REDIS_FAULTS, TypeError)

#: What acquiring the client can fail with: get_redis_client documents RuntimeError on a failed
#: connect, the transport raises REDIS_FAULTS, and a malformed URL raises ValueError. Anything else
#: is a bug in our own code and must not read as "Redis is down".
_ACQUIRE_FAULTS: tuple[type[BaseException], ...] = (*REDIS_FAULTS, RuntimeError, ValueError)


async def best_effort_redis_client() -> RedisClient | None:
    """Return a Redis client when available; ``None`` when Redis is down or unconfigured.

    Chart/overlay query services use this to skip Redis short-circuit paths without
    failing the HTTP request — the services fall through to DB/exchange fetchers.
    """
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        return await get_redis_client()
    except _ACQUIRE_FAULTS:
        logger.debug("best_effort_redis_client: Redis unavailable — continuing without cache")
        return None


__all__ = ["REDIS_CACHE_WRITE_FAULTS", "REDIS_FAULTS", "best_effort_redis_client"]
