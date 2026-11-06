"""Behavior tests for shared Redis async resource shutdown."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestCloseRedisResource:
    @pytest.mark.asyncio
    async def test_prefers_aclose_when_available(self) -> None:
        """Use the modern async Redis shutdown API when present."""
        from src.infrastructure.cache.redis_resource_close import close_redis_resource

        resource = MagicMock()
        resource.aclose = AsyncMock()
        resource.close = AsyncMock()

        await close_redis_resource(resource)

        resource.aclose.assert_awaited_once()
        resource.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_close_for_older_clients(self) -> None:
        """Keep compatibility with Redis resources that only expose close()."""
        from src.infrastructure.cache.redis_resource_close import close_redis_resource

        resource = MagicMock(spec=["close"])
        resource.close = AsyncMock()

        await close_redis_resource(resource)

        resource.close.assert_awaited_once()
