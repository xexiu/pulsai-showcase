"""Redis flag store for the polling-task short-circuit gate.

Each named subsystem (demo brackets, paper brackets, paper pending fills,
paper limit-order lifecycle) has one flat Redis key. Pollers EXISTS-check
the key before opening a DB session or making an exchange HTTP call; user
actions (e.g. placing a demo bracket) SET it.

Fail-open contract:
- read errors return ``True`` (assume work present, never silently drop a
  reconciliation pass);
- write/delete errors are swallowed (the poller's DB-fallback path will
  re-assert truth on the next tick).

SoT for the key shape: :meth:`CacheKeys.trading_activity_flag`.
SoT for the TTL:       :data:`CacheKeys.TTL_TRADING_ACTIVITY_FLAG`.
SoT for subsystem ids: :mod:`src.shared.constants.trading_activity_flags`.
"""

from __future__ import annotations

import logging

from src.infrastructure.cache.keys import CacheKeys

logger = logging.getLogger(__name__)


async def mark_active(system: str) -> None:
    """Assert that ``system`` has open work; pollers will fully process the next tick."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        await redis.set(
            CacheKeys.trading_activity_flag(system=system),
            "1",
            ex=CacheKeys.TTL_TRADING_ACTIVITY_FLAG,
        )
    except Exception as exc:
        logger.warning("trading_activity_flags.mark_active(%s) skipped: %s", system, exc)


async def has_active(system: str) -> bool:
    """Return True iff ``system`` is currently marked as having open work.

    Fails open: returns True on Redis errors so the poller still runs its
    DB-truth fallback rather than silently sleeping.
    """
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        result = await redis.exists(CacheKeys.trading_activity_flag(system=system))
        return bool(result)
    except Exception as exc:
        logger.warning("trading_activity_flags.has_active(%s) fail-open: %s", system, exc)
        return True


async def clear_active(system: str) -> None:
    """Remove ``system``'s flag. Used by the daily reconciler when DB has no open work."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        await redis.delete(CacheKeys.trading_activity_flag(system=system))
    except Exception as exc:
        logger.warning("trading_activity_flags.clear_active(%s) skipped: %s", system, exc)


__all__ = ["clear_active", "has_active", "mark_active"]
