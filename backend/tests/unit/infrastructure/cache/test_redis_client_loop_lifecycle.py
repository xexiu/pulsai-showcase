"""BEHAVIOR: stale async Redis clients must be disposed on loop change."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.cache.redis_client_loop_lifecycle import (
    dispose_stale_redis_client_best_effort,
)


@pytest.mark.asyncio
async def test_dispose_stale_redis_client_calls_close_first() -> None:
    stale = MagicMock()
    stale.close = AsyncMock()
    stale._pool = None
    stale._client = MagicMock()

    await dispose_stale_redis_client_best_effort(stale)

    stale.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispose_stale_redis_client_disconnects_pool_when_close_fails() -> None:
    stale = MagicMock()
    stale.close = AsyncMock(side_effect=RuntimeError("Event loop is closed"))
    pool = MagicMock()
    pool.disconnect = AsyncMock()
    stale._pool = pool
    stale._client = MagicMock()

    await dispose_stale_redis_client_best_effort(stale)

    pool.disconnect.assert_awaited_once()
    assert stale._client is None
    assert stale._pool is None
