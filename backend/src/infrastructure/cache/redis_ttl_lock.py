"""Shared Redis SETNX-with-TTL lock helper.

Phase 9 — Track A (Finding 7). Before this module, every caller that
needed a short-lived "I own this work" lock (paper-trading lifecycle
order sweep, paper-trading position sweep) re-implemented the same
SETNX + ``ex=`` + best-effort ``DELETE`` in slightly different ways:
subtle drift on the lock-token value, on exception handling, on whether
the release step was guarded by acquisition success. This module is the
one implementation, used by any new SETNX lock call site.

Contract summary:

- :func:`acquire_ttl_lock` — ``redis.set(key, token, nx=True, ex=ttl_s)``
  and ``bool``-coerces the response so ``"OK"`` / ``True`` both mean
  acquired. The token itself is opaque; we default to ``"1"`` because
  it matches the pre-existing worker implementation (wire parity).
- :func:`release_ttl_lock` — deletes the key only while it still holds the
  caller's token (WATCH/MULTI compare-and-delete), with a DEBUG-logged
  failure path. The TTL is the safety net if release ever drops on the
  floor, so we NEVER raise from here and risk killing a caller that
  already did the real work.
- :func:`ttl_lock` — async CM wrapper; yields the acquisition ``bool``,
  releases on exit ONLY if we actually acquired. That "only if" is
  critical: if SETNX loses the race another worker owns the key, and
  calling ``DELETE`` would steal that other worker's lock.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final, Protocol, cast
from uuid import uuid4

from redis.exceptions import WatchError

from src.infrastructure.cache.redis_best_effort import REDIS_FAULTS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import redis.asyncio as redis

    from src.infrastructure.cache.redis_client import RedisClient

    #: the app's wrapper (``RedisClient``: ``set(nx=, ex=)`` and ``pipeline(transaction=)``), its decoded raw
    #: client (``Redis[str]``) or a bytes client -- every one of them can hold and release a lock.
    LockRedis = RedisClient | redis.Redis[str] | redis.Redis[bytes]

    class WatchedPipeline(Protocol):
        """The six pipeline calls a compare-and-delete makes, with the result types it relies on."""

        async def watch(self, *_names: str) -> object: ...
        async def get(self, _name: str, /) -> str | bytes | None: ...
        async def unwatch(self) -> object: ...
        def multi(self) -> None: ...
        def delete(self, *_names: str) -> object: ...
        async def execute(self) -> list[object]: ...


logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_LOCK_TOKEN",
    "acquire_ttl_lock",
    "release_ttl_lock",
    "ttl_lock",
]

DEFAULT_LOCK_TOKEN: Final[str] = "1"
"""Opaque value written into Redis when acquiring a SETNX lock. No semantics —
presence of the key is the lock. ``"1"`` matches every pre-Phase-9 SETNX
caller in the codebase."""


async def acquire_ttl_lock(
    redis_client: LockRedis,
    key: str,
    *,
    ttl_s: int,
    token: str = DEFAULT_LOCK_TOKEN,
) -> bool:
    """SETNX ``key`` with a ``ttl_s``-second TTL. Return ``True`` iff acquired.

    Bool-coerces the redis-client response: asyncio-redis returns ``True`` /
    ``None``; some proxies return ``"OK"`` / ``None``. Either way, truthy
    = acquired.
    """
    return bool(
        await redis_client.set(key, token, nx=True, ex=ttl_s),
    )


async def release_ttl_lock(redis_client: LockRedis, key: str, *, token: str) -> bool:
    """Delete ``key`` only while it still holds ``token``; True iff this call released it. Never raises.

    A bare DELETE released whatever the key held: a holder whose TTL lapsed mid-work deleted the NEXT
    holder's lock, which is the mutual-exclusion break this module exists to prevent (reproduced
    2026-11-06 on fakeredis). The check and the delete are one optimistic transaction -- WATCH, read,
    MULTI/DELETE/EXEC -- so a key re-taken between the read and the delete aborts the EXEC rather than
    losing the other holder's lock. No Lua, so it runs on any Redis-protocol server and on fakeredis.

    The TTL still catches any orphaned key, so a failed release costs latency, never correctness.
    """
    try:
        async with redis_client.pipeline(transaction=True) as raw_pipe:
            pipe = cast("WatchedPipeline", raw_pipe)  # redis-py types execute() as a partly unknown list
            await pipe.watch(key)
            current = await pipe.get(key)
            held = current.decode() if isinstance(current, bytes) else current
            if held != token:
                await pipe.unwatch()
                return False
            pipe.multi()
            pipe.delete(key)
            await pipe.execute()
            return True
    except WatchError:
        return False  # re-taken between the read and the delete: it is someone else's lock now
    except REDIS_FAULTS as exc:
        logger.debug("redis_ttl_lock_release_failed key=%s error=%s", key, exc)
        return False


@asynccontextmanager
async def ttl_lock(
    redis_client: LockRedis,
    key: str,
    *,
    ttl_s: int,
    token: str | None = None,
) -> AsyncIterator[bool]:
    """Async context manager — acquire on entry, release on exit iff acquired and still ours.

    Each entry writes its own token (a fresh UUID unless one is given), so the release can tell this
    holder's lock from the next holder's after a TTL lapse.

    Usage::

        async with ttl_lock(redis_client, lock_key, ttl_s=45) as acquired:
            if not acquired:
                return "skipped_lock"
            ... do the work ...

    The "only if acquired" release guard is essential — calling DELETE on
    a key owned by another worker would break mutual exclusion.
    """
    holder_token = token if token is not None else uuid4().hex
    acquired = await acquire_ttl_lock(redis_client, key, ttl_s=ttl_s, token=holder_token)
    try:
        yield acquired
    finally:
        if acquired:
            await release_ttl_lock(redis_client, key, token=holder_token)
