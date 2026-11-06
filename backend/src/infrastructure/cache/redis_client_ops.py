"""
Redis data-structure operation mixin.

Provides string / JSON / hash / list / counter / TTL / sorted-set / pipeline
operations as a mixin so :class:`src.infrastructure.cache.redis_client.RedisClient`
stays focused on connection lifecycle and singleton management.

The mixin requires a concrete ``self.client`` property returning the underlying
``redis.asyncio.Redis[str]`` instance — declared via ``TYPE_CHECKING`` so type
checkers recognize it without producing a runtime attribute.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeAlias, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    import redis.asyncio as redis
    from redis.asyncio.client import Pipeline

# Redis type aliases for hset mapping (Python 3.11 compatible)
RedisKey: TypeAlias = str | bytes
RedisValue: TypeAlias = str | bytes | int | float

logger = logging.getLogger(__name__)


class RedisDataOps:
    """
    Mixin providing Redis data-structure operations.

    Requires the concrete class to expose ``self.client`` as a
    ``redis.asyncio.Redis[str]`` property — see :class:`RedisClient` for the
    canonical implementation that raises ``RuntimeError`` when not connected.
    """

    if TYPE_CHECKING:

        @property
        def client(self) -> redis.Redis[str]: ...

    # ==================== String Operations ====================

    async def get(self, key: str) -> str | None:
        """
        Get a string value from Redis.

        Args:
            key: The cache key

        Returns:
            The value or None if not found
        """
        return await self.client.get(key)

    async def mget(self, keys: Sequence[str]) -> list[str | None]:
        """
        Get several string values in ONE round trip (Redis ``MGET``), aligned 1:1 with ``keys``.

        Added 2026-11-06: econ_event_alerts._read_dedup called it on the shared client, which had no ``mget``, so every
        due econ alert raised AttributeError (pulsai.log 13:30 / 13:31 UTC) while its tests passed on a double that had one.

        Args:
            keys: The cache keys

        Returns:
            One value per key, None where the key is absent; no round trip for no keys
        """
        if not keys:
            return []
        return list(await self.client.mget(list(keys)))

    async def getdel(self, key: str) -> str | None:
        """
        Atomically read a key and delete it (Redis ``GETDEL``, server 6.2+).

        One round trip where ``get`` + ``delete`` is two — but the round trips are not the
        point. ATOMICITY is: a read-then-delete pair lets two callers both observe the same
        value before either clears it, which turns a one-shot flag into a duplicated action.
        The spike watcher's outstanding-page flag is exactly that shape, and two API replicas
        observing one healthy tick must not both announce recovery.

        Args:
            key: The cache key

        Returns:
            The value, or None if the key did not exist
        """
        return await self.client.getdel(key)

    async def set(
        self,
        key: str,
        value: str | bytes | int | float,
        ex: int | None = None,
        *,
        nx: bool = False,
    ) -> bool:
        """
        Set a string value in Redis.

        Args:
            key: The cache key
            value: The value to store
            ex: Expiration time in seconds (optional)
            nx: When True, SET only if key does not exist (SETNX semantics).

        Returns:
            True if the value was written. With ``nx=True``, returns False when
            the key already existed (redis-py returns ``None`` in that case).
        """
        result = await self.client.set(key, value, ex=ex, nx=nx)  # redis-py reads ex=None / nx=False as not given
        return result is True

    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.

        Args:
            keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        if not keys:
            return 0
        result = await self.client.delete(*keys)
        return int(result)

    async def exists(self, *keys: str) -> int:
        """
        Check if keys exist.

        Args:
            keys: Keys to check

        Returns:
            Number of keys that exist
        """
        if not keys:
            return 0
        result = await self.client.exists(*keys)
        return int(result)

    # ==================== JSON Operations (via strings) ====================

    async def get_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        """
        Get a JSON value from Redis.

        Uses orjson for fast deserialization.

        Args:
            key: The cache key

        Returns:
            The deserialized JSON or None if not found
        """
        import orjson

        value = await self.client.get(key)
        if value is None:
            return None

        try:
            result: dict[str, Any] | list[Any] | None = orjson.loads(value)
            return result
        except orjson.JSONDecodeError:
            logger.warning("Failed to decode JSON for key %s", key)
            return None

    async def set_json(
        self,
        key: str,
        value: dict[str, Any] | list[Any],
        ex: int | None = None,
    ) -> bool:
        """
        Set a JSON value in Redis.

        Uses orjson for fast serialization.

        Args:
            key: The cache key
            value: The value to store (must be JSON-serializable)
            ex: Expiration time in seconds (optional)

        Returns:
            True if successful
        """
        import orjson

        try:
            json_bytes = orjson.dumps(value)
            result = await self.client.set(key, json_bytes, ex=ex)
            return result is True
        except TypeError as e:
            logger.exception("Failed to serialize JSON for key %s: %s", key, e)
            return False

    # ==================== Hash Operations ====================

    async def hget(self, name: str, key: str) -> str | None:
        """Get a hash field value."""
        return await self.client.hget(name, key)

    async def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: dict[str, str] | None = None,
    ) -> int:
        """
        Set hash field(s).

        Args:
            name: Hash name
            key: Field name (if setting single field)
            value: Field value (if setting single field)
            mapping: Dict of field-value pairs (if setting multiple)

        Returns:
            Number of fields added
        """
        if mapping is not None:
            # Cast to satisfy redis-py's Mapping[_Key, _Value] type
            redis_mapping = cast("Mapping[RedisKey, RedisValue]", mapping)
            result = await self.client.hset(name, mapping=redis_mapping)
        elif key is not None and value is not None:
            result = await self.client.hset(name, key, value)
        else:
            msg = "Must provide either (key, value) or mapping"
            raise ValueError(msg)
        return int(result)

    async def hgetall(self, name: str) -> dict[str, str]:
        """Get all fields and values from a hash."""
        result = await self.client.hgetall(name)
        return dict(result) if result else {}

    # ==================== List Operations ====================

    async def lpush(self, name: str, *values: str) -> int:
        """Push values to the head of a list."""
        result = await self.client.lpush(name, *values)
        return int(result)

    async def rpush(self, name: str, *values: str) -> int:
        """Push values to the tail of a list."""
        result = await self.client.rpush(name, *values)
        return int(result)

    async def lrange(self, name: str, start: int, end: int) -> list[str]:
        """Get a range of elements from a list."""
        result = await self.client.lrange(name, start, end)
        return list(result)

    async def ltrim(self, name: str, start: int, end: int) -> bool:
        """Trim a list to the specified range."""
        result = await self.client.ltrim(name, start, end)
        return result is True

    # ==================== Increment Operations ====================

    async def incr(self, key: str) -> int:
        """Increment a key's integer value by 1."""
        result = await self.client.incr(key)
        return int(result)

    async def incrby(self, key: str, amount: int) -> int:
        """Increment a key's integer value by amount."""
        result = await self.client.incrby(key, amount)
        return int(result)

    # ==================== TTL Operations ====================

    async def expire(self, key: str, seconds: int) -> bool:
        """Set a key's time to live in seconds."""
        result = await self.client.expire(key, seconds)
        return bool(result)

    async def ttl(self, key: str) -> int:
        """Get a key's time to live in seconds."""
        result = await self.client.ttl(key)
        return int(result)

    # ==================== Scan / Sorted Set (abuse log, IP block list) ====================

    async def scan_keys(
        self,
        pattern: str,
        *,
        count: int = 256,
    ) -> list[str]:
        """Return keys matching pattern (non-blocking SCAN, not KEYS *)."""
        return [key async for key in self.client.scan_iter(match=pattern, count=count)]

    async def zadd(self, name: str, mapping: dict[str, float]) -> int:
        """Add members to a sorted set (member -> score)."""
        score_mapping = cast(
            "Mapping[str | bytes, bytes | float | int | str]",
            mapping,
        )
        result = await self.client.zadd(name, score_mapping)
        return int(result)

    async def zrevrange(self, name: str, start: int, end: int, *, withscores: bool = False) -> list[str] | list[tuple[str, float]]:
        """Return members from sorted set, highest score first."""
        result = await self.client.zrevrange(
            name,
            start,
            end,
            withscores=withscores,
        )
        if withscores:
            pairs = cast("list[tuple[Any, Any]]", result)
            return [(str(m), float(s)) for m, s in pairs]
        members = cast("list[Any]", result)
        return [str(x) for x in members]

    async def zremrangebyrank(self, name: str, start: int, end: int) -> int:
        """Remove members in rank range."""
        result = await self.client.zremrangebyrank(name, start, end)
        return int(result)

    async def llen(self, name: str) -> int:
        """Length of a list -- the pending depth of a Celery queue.

        Added for the worker-starvation health check, which needs a queue's backlog to tell a
        starving queue from an idle one. Reaching past this wrapper for the raw client would work
        and is exactly the shortcut that leaves one call site with no timeout, no metrics and no
        test double, so the operation is added here where every other Redis verb lives.
        """
        result = await self.client.llen(name)
        return int(result)

    async def zcard(self, name: str) -> int:
        """Cardinality of sorted set."""
        result = await self.client.zcard(name)
        return int(result)

    # ==================== Pipeline Operations ====================

    @asynccontextmanager
    async def pipeline(
        self,
        transaction: bool = True,
    ) -> AsyncIterator[Pipeline[str]]:
        """
        Create a pipeline for batched operations.

        Pipelines reduce round-trips to Redis for better performance.

        Args:
            transaction: If True, wrap in MULTI/EXEC (atomic)

        Yields:
            Pipeline object

        Example:
            async with client.pipeline() as pipe:
                await pipe.set("key1", "value1")
                await pipe.set("key2", "value2")
                await pipe.execute()
        """
        async with self.client.pipeline(transaction=transaction) as pipe:
            yield pipe
