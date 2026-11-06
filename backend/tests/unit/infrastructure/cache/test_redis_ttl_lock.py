"""Phase 9 Track A — Finding 7: shared Redis SETNX-with-TTL lock helper.

Hoists the SETNX + ``ex=`` + best-effort ``DELETE`` pattern out of the
paper-trading worker into :mod:`src.infrastructure.cache.redis_ttl_lock`
so every caller (order sweep, position sweep, future lifecycle
supervisor) uses one implementation.

Contract:

- :func:`acquire_ttl_lock` — calls ``redis.set(key, token, nx=True, ex=ttl_s)``;
  returns ``True`` iff the key was newly set. Bool coercion so a venue-specific
  ``OK`` string (``"OK"``) or the raw Python ``True`` both mean "acquired".
- :func:`release_ttl_lock` — calls ``redis.delete(key)``; logs at DEBUG
  and swallows on failure because the TTL is the safety net.
- :func:`ttl_lock` (async CM) — yields the acquisition boolean and
  releases on exit only if we actually acquired.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import fakeredis
import pytest
from redis import exceptions as redis_exceptions

from src.infrastructure.cache.redis_ttl_lock import (
    acquire_ttl_lock,
    release_ttl_lock,
    ttl_lock,
)


class TestAcquireTtlLock:
    @pytest.mark.asyncio
    async def test_acquire_success_returns_true(self) -> None:
        redis = AsyncMock()
        redis.set.return_value = True
        acquired = await acquire_ttl_lock(redis, "paper:lifecycle:x", ttl_s=45)
        assert acquired is True
        redis.set.assert_awaited_once_with("paper:lifecycle:x", "1", nx=True, ex=45)

    @pytest.mark.asyncio
    async def test_acquire_failure_returns_false(self) -> None:
        redis = AsyncMock()
        redis.set.return_value = None  # Redis returns None when nx=True key already set.
        acquired = await acquire_ttl_lock(redis, "paper:lifecycle:x", ttl_s=45)
        assert acquired is False

    @pytest.mark.asyncio
    async def test_acquire_with_custom_token(self) -> None:
        redis = AsyncMock()
        redis.set.return_value = True
        await acquire_ttl_lock(redis, "k", ttl_s=60, token="worker-7")
        redis.set.assert_awaited_once_with("k", "worker-7", nx=True, ex=60)

    @pytest.mark.asyncio
    async def test_acquire_coerces_truthy_string_to_true(self) -> None:
        """Some async redis clients return ``"OK"`` on success — must be ``True``."""
        redis = AsyncMock()
        redis.set.return_value = "OK"
        acquired = await acquire_ttl_lock(redis, "k", ttl_s=45)
        assert acquired is True


class TestReleaseTtlLock:
    @pytest.mark.asyncio
    async def test_release_swallows_redis_errors(self, caplog: pytest.LogCaptureFixture) -> None:
        redis = MagicMock()
        redis.pipeline.side_effect = redis_exceptions.ConnectionError("redis transient")
        with caplog.at_level(logging.DEBUG, logger="src.infrastructure.cache.redis_ttl_lock"):
            assert await release_ttl_lock(redis, "paper:lifecycle:x", token="t") is False
        assert any("paper:lifecycle:x" in record.message for record in caplog.records)


class TestOwnershipOnARealRedis:
    """The race the mocks cannot see: a holder whose TTL lapsed must not delete the NEXT holder's lock."""

    @pytest.mark.asyncio
    async def test_a_holder_whose_lock_expired_does_not_release_the_next_holders_lock(self) -> None:
        redis = fakeredis.aioredis.FakeRedis()
        async with ttl_lock(redis, "k", ttl_s=45) as acquired:
            assert acquired is True
            await redis.delete("k")  # A's TTL lapses mid-work ...
            assert await acquire_ttl_lock(redis, "k", ttl_s=45, token="worker-b")  # ... and B takes the lock
        assert await redis.get("k") == b"worker-b"  # A's exit left B's lock alone

    @pytest.mark.asyncio
    async def test_release_deletes_only_the_holders_own_token(self) -> None:
        redis = fakeredis.aioredis.FakeRedis()
        await acquire_ttl_lock(redis, "k", ttl_s=45, token="mine")
        assert await release_ttl_lock(redis, "k", token="theirs") is False
        assert await redis.get("k") == b"mine"
        assert await release_ttl_lock(redis, "k", token="mine") is True
        assert await redis.get("k") is None

    @pytest.mark.asyncio
    async def test_two_holders_get_different_tokens(self) -> None:
        redis = fakeredis.aioredis.FakeRedis()
        async with ttl_lock(redis, "a", ttl_s=45):
            first = await redis.get("a")
        async with ttl_lock(redis, "a", ttl_s=45):
            second = await redis.get("a")
        assert first != second


class TestTtlLockContextManager:
    @pytest.mark.asyncio
    async def test_releases_when_acquired(self) -> None:
        redis = fakeredis.aioredis.FakeRedis()
        async with ttl_lock(redis, "k", ttl_s=45) as acquired:
            assert acquired is True
            assert await redis.get("k") is not None
        assert await redis.get("k") is None

    @pytest.mark.asyncio
    async def test_does_not_release_when_not_acquired(self) -> None:
        """If SETNX says someone else owns the lock we MUST NOT DELETE their key."""
        redis = fakeredis.aioredis.FakeRedis()
        await redis.set("k", "other")
        async with ttl_lock(redis, "k", ttl_s=45) as acquired:
            assert acquired is False
        assert await redis.get("k") == b"other"

    @pytest.mark.asyncio
    async def test_releases_on_exception_inside_block(self) -> None:
        redis = fakeredis.aioredis.FakeRedis()
        with pytest.raises(RuntimeError):
            async with ttl_lock(redis, "k", ttl_s=45):
                raise RuntimeError("boom")
        assert await redis.get("k") is None
