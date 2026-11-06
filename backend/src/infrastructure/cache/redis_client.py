"""
Async Redis Client with Connection Pooling

Provides a singleton async Redis client with:
- Connection pooling via hiredis for < 2ms operations
- Automatic reconnection
- Graceful shutdown
- Type-safe operations

Sibling modules:
- :mod:`redis_client_ops` — ``RedisDataOps`` mixin contributing the
  string / JSON / hash / list / counter / TTL / sorted-set / pipeline methods.

@see docs/02-technical/TECH_STACK.md - Redis Configuration
@see https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
"""

from __future__ import annotations

import asyncio
import logging
from typing import cast

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from src.infrastructure.cache.redis_client_loop_lifecycle import (
    dispose_stale_redis_client_best_effort,
)
from src.infrastructure.cache.redis_client_ops import RedisDataOps
from src.infrastructure.cache.redis_connections import (
    get_async_redis_connection_kwargs,
    resolve_redis_url,
)
from src.infrastructure.cache.redis_resource_close import close_redis_resource
from src.shared.constants.resource_pools import DEFAULT_REDIS_MAX_CONNECTIONS

logger = logging.getLogger(__name__)

# Module-level singleton
_redis_client: RedisClient | None = None
_redis_client_init_lock: asyncio.Lock | None = None
# id(asyncio.get_running_loop()) when _redis_client was created; Celery uses
# run_async_from_sync → asyncio.run() per task, so each task gets a new loop.
# Without rebinding, the second task reuses a client tied to a closed loop
# ("Event loop is closed" on snapshot writes, market_limits TTL probes, etc.).
_redis_singleton_loop_id: int | None = None


class RedisClient(RedisDataOps):
    """
    Async Redis client wrapper with connection pool management.

    This class provides:
    - Singleton pattern for application-wide client reuse
    - Connection pooling for efficient connection management
    - Health check and reconnection capabilities
    - Graceful shutdown

    Data-structure operations (get/set/hget/lpush/zadd/pipeline/…) are
    contributed by :class:`RedisDataOps` so this class can stay focused on
    lifecycle. The mixin reads ``self.client`` (defined below).

    Performance Target: < 2ms per operation (with hiredis)

    Example:
        client = await get_redis_client()
        await client.set("key", "value", ex=60)
        value = await client.get("key")
    """

    def __init__(
        self,
        redis_url: str,
        max_connections: int | None = None,
        *,
        socket_timeout: float | None = None,
    ) -> None:
        """
        Initialize Redis client.

        Args:
            redis_url: Redis connection URL (redis://host:port)
            max_connections: Maximum pool connections (default: 50)
            socket_timeout: Per-operation read/write timeout seconds; ``None`` uses
                the shared default (5s). Use a larger value for rare huge payloads
                (e.g. CCXT market template SET) so concurrent Celery prewarms do not
                hit ``Timeout writing to socket`` under local/dev Redis load.
        """
        self._url = redis_url
        self._max_connections = max_connections if max_connections is not None else DEFAULT_REDIS_MAX_CONNECTIONS
        self._socket_timeout: float | None = socket_timeout
        self._pool: ConnectionPool[redis.Connection] | None = None
        self._client: redis.Redis[str] | None = None

    async def connect(self) -> None:
        """
        Initialize connection pool and client.

        Creates a connection pool with hiredis parser for maximum performance.
        Uses RESP protocol 3 for modern Redis features.
        """
        if self._client is not None:
            logger.debug("Redis client already connected")
            return

        try:
            # Create connection pool with hiredis parser
            # hiredis provides C-level parsing for ~10x speedup
            st = self._socket_timeout if self._socket_timeout is not None else 5.0
            self._pool = ConnectionPool.from_url(
                self._url,
                **get_async_redis_connection_kwargs(
                    max_connections=self._max_connections,
                    socket_timeout=st,
                ),
            )

            # Create client from pool
            # Type cast needed: decode_responses=True in pool makes it Redis[str]
            self._client = cast(
                "redis.Redis[str]",
                redis.Redis(connection_pool=self._pool),
            )

            # Verify connection (also primes the connection pool so the
            # subsequent metrics wrapper does not bill pool-acquire cost to
            # the first observed command). Log the pre-wrap PING latency
            # so SREs can confirm the wrapper-after-ping fix is in effect.
            import time as _time

            _pre_ping_start = _time.perf_counter()
            await self._client.ping()
            _pre_ping_ms = (_time.perf_counter() - _pre_ping_start) * 1000.0
            # DEBUG, not INFO: Celery runs each task on a fresh asyncio.run() loop, so the
            # loop-bound async pool reconnects per task — at INFO this floods the log (see the
            # get_redis_client docstring). Routine lifecycle belongs at DEBUG.
            logger.debug(
                "Redis connected successfully to %s (pre-wrap ping=%.2fms)",
                self._url,
                _pre_ping_ms,
            )

            # Install Prometheus duration wrapper AFTER ping() so cold
            # connection-pool acquisition is excluded from observed
            # percentiles. Wrapped in try/except since observability must
            # never break the API path. Logs a post-wrap PING to confirm
            # the steady-state latency floor reaching observability.
            try:
                from src.infrastructure.observability.redis_metrics import (
                    install_redis_command_wrapper,
                )

                install_redis_command_wrapper(self._client)
                _post_ping_start = _time.perf_counter()
                await self._client.ping()
                _post_ping_ms = (_time.perf_counter() - _post_ping_start) * 1000.0
                logger.debug("redis_metrics_wrapper_installed post_wrap_ping_ms=%.2f", _post_ping_ms)
            except Exception as exc:
                logger.warning("install_redis_command_wrapper_failed: %s", exc)

        except redis.RedisError as e:
            logger.exception("Failed to connect to Redis: %s", e)
            self._client = None
            self._pool = None
            raise

    async def close(self) -> None:
        """
        Close client and pool connections gracefully.

        Should be called during application shutdown.
        """
        # Drop the handles BEFORE awaiting the closes. Same ordering defect as
        # `close_redis_client`: `disconnect()` raises on a connection from a dead loop, and the
        # old code cleared `self._pool` only after that await, so a failed close left the dead
        # pool attached to be reused (SIGNAL-LOOP-1).
        client, pool = self._client, self._pool
        self._client = None
        self._pool = None

        if client is not None:
            await close_redis_resource(client)
            logger.debug("Redis client closed")

        if pool is not None:
            await pool.disconnect()
            logger.debug("Redis connection pool closed")

    async def ping(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if connected, False otherwise
        """
        if self._client is None:
            return False
        try:
            await self._client.ping()
            return True
        except redis.RedisError:
            return False

    def is_connected(self) -> bool:
        """Whether a live handle is held: False before ``connect()`` and after ``close()``.

        Consumers check this instead of catching the ``RuntimeError`` that ``client`` raises, so a
        read racing lifespan teardown (or degraded no-Redis mode) is a quiet cache miss rather than
        an ERROR + traceback (SHUTDOWNREDIS-1). Same spelling as the websocket and book-ticker feeds.
        """
        return self._client is not None

    @property
    def client(self) -> redis.Redis[str]:
        """
        Get the underlying Redis client.

        Raises:
            RuntimeError: If not connected

        Returns:
            The Redis async client
        """
        if self._client is None:
            msg = "Redis client not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._client


async def get_redis_client() -> RedisClient:
    """
    Get or create the singleton Redis client.

    This function is the primary way to access Redis throughout the
    application.
    It ensures a single connection pool is reused **per running event loop**.

    Celery tasks that use :func:`run_async_from_sync` get a fresh ``asyncio.run()``
    loop per invocation; the previous loop is closed when the call returns.
    In that case we dispose the stale singleton's pool before rebinding on the
    current loop. Celery tasks also call :func:`close_redis_client` in a
    ``finally`` block via :func:`run_async_from_sync` when ``from_celery=True``.

    Returns:
        The initialized Redis client

    Raises:
        RuntimeError: If connection fails
    """
    global _redis_client, _redis_client_init_lock, _redis_singleton_loop_id

    try:
        running_loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        running_loop_id = None

    if (
        _redis_client is not None
        and running_loop_id is not None
        and _redis_singleton_loop_id is not None
        and running_loop_id != _redis_singleton_loop_id
    ):
        logger.debug(
            "Async Redis singleton was bound to another event loop; disposing stale client before rebind (Celery/run_async_from_sync)",
        )
        stale_client = _redis_client
        _redis_client = None
        _redis_client_init_lock = None
        _redis_singleton_loop_id = None
        await dispose_stale_redis_client_best_effort(stale_client)

    if _redis_client is None:
        if _redis_client_init_lock is None:
            # Create the lock lazily in the current event-loop context.
            _redis_client_init_lock = asyncio.Lock()

        async with _redis_client_init_lock:
            if _redis_client is None:
                _redis_client = RedisClient(
                    redis_url=resolve_redis_url(),
                    max_connections=DEFAULT_REDIS_MAX_CONNECTIONS,
                )
                await _redis_client.connect()
                _redis_singleton_loop_id = id(asyncio.get_running_loop())

    return _redis_client


async def close_redis_client() -> None:
    """
    Close the singleton Redis client.

    Should be called during application shutdown.
    """
    global _redis_client, _redis_client_init_lock, _redis_singleton_loop_id

    client = _redis_client
    bound_loop_id = _redis_singleton_loop_id
    try:
        running_loop_id: int | None = id(asyncio.get_running_loop())
    except RuntimeError:
        running_loop_id = None

    # A SINGLETON FROM ANOTHER LOOP IS DISPOSED, NOT CLOSED-AND-REPORTED.
    #
    # `get_redis_client` already detects this mismatch on the way IN and routes it through
    # `dispose_stale_redis_client_best_effort`, which logs at DEBUG. The way OUT had no such
    # check, and `run_async_from_sync(from_celery=True)` closes the singleton in a `finally`
    # whether or not the task touched Redis at all -- so a client bound to a torn-down loop got
    # `pool.disconnect()` called on dead transports.
    #
    # MEASURED in pulsai.log over 2026-08-31 07:54 -> 2026-09-01 13:35: 170 `RuntimeError: Event
    # loop is closed`, 161 "Redis cleanup after the Celery task failed" -- a full traceback per
    # Celery task, for a condition the codebase already handles one function away. Not a leak
    # (connected_clients measured 78 with a healthy command mix); noise, and noise that trains a
    # reader to skim tracebacks. Same helper, so there is one disposal rule rather than two.
    #
    # The mismatch must be KNOWN to take this path: with no recorded loop id nothing is known
    # about provenance, and inventing a reason to go quiet is how a real failure disappears.
    is_foreign_loop = bound_loop_id is not None and running_loop_id is not None and bound_loop_id != running_loop_id

    # Reset ALWAYS, even when the close raises. SIGNAL-LOOP-1: a connection created on a
    # since-closed event loop makes `close()` raise, and the old ordering cleared the globals
    # only AFTER that await -- so the poisoned singleton stayed installed and every later task
    # in the worker reused it and failed identically, forever (22 of 23 runs, never recovering).
    # Clearing first makes the next task build a fresh client on its own loop, which turns a
    # permanent outage into one logged hiccup. On the SAME loop the exception still reaches the
    # caller, so the caller decides whether it is fatal.
    try:
        if client is None:
            return
        if is_foreign_loop:
            await dispose_stale_redis_client_best_effort(client)
            return
        await client.close()
    finally:
        _redis_client = None
        _redis_client_init_lock = None
        _redis_singleton_loop_id = None


def reset_redis_client() -> None:
    """
    Reset the singleton Redis client without closing.

    Used in tests to force re-initialization in the correct event loop.
    This does NOT close existing connections - use close_redis_client()
    for graceful shutdown.

    WHY: When using sync TestClient, each test may run in a different
    event loop context. The Redis client singleton must be reset so it
    re-initializes in the new loop's context.
    """
    global _redis_client, _redis_client_init_lock, _redis_singleton_loop_id
    _redis_client = None
    _redis_client_init_lock = None
    _redis_singleton_loop_id = None
