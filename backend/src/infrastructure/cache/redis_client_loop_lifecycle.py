"""Lifecycle helpers for the async Redis singleton across event-loop boundaries.

Celery tasks use ``run_async_from_sync`` → ``asyncio.run()`` per invocation.
Without disposing the previous loop's pool, connection threads leak until the OS
refuses new threads (``can't start new thread``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.cache.redis_client import RedisClient

logger = logging.getLogger(__name__)

__all__ = [
    "dispose_stale_redis_client_best_effort",
]


async def dispose_stale_redis_client_best_effort(stale: RedisClient) -> None:
    """Close *stale* Redis client/pool; swallow errors from dead foreign loops."""
    try:
        await stale.close()
        return
    except Exception:
        logger.debug(
            "stale_redis_client_close_failed_trying_pool_disconnect",
            exc_info=True,
        )

    pool = stale._pool  # intentional lifecycle teardown — private attrs
    stale._client = None
    stale._pool = None
    if pool is None:
        return
    try:
        await pool.disconnect()
    except Exception:
        logger.debug("stale_redis_pool_disconnect_failed", exc_info=True)
