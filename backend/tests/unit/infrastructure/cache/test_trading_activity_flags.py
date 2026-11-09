"""Tests for trading activity flag cache (poller short-circuit gate).

Polling tasks (demo brackets, paper brackets, paper fills, paper lifecycle)
should skip their expensive HTTP + DB work when no user has open activity in
that subsystem. A small Redis flag with TTL gives them a cheap O(1) check.

Behavior under test:
- ``mark_active(system)`` SETs the flag with a finite TTL
- ``has_active(system)`` returns True iff the flag exists
- ``clear_active(system)`` removes the flag (used by daily reconciler)
- All paths fail open (return safe defaults) when Redis is unreachable
- Key namespace lives on :class:`CacheKeys` (SoT — no inline f-strings)
- Subsystem names are typed (no stringly-typed callers)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestCacheKeyTradingActivityFlag:
    def test_builder_returns_namespaced_key(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        key = CacheKeys.trading_activity_flag(system="demo_brackets")
        assert key == "trading_activity:active:demo_brackets"

    def test_builder_stable_across_invocations(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        a = CacheKeys.trading_activity_flag(system="paper_brackets")
        b = CacheKeys.trading_activity_flag(system="paper_brackets")
        assert a == b

    @pytest.mark.parametrize("system", ["", " "])
    def test_builder_rejects_empty_system(self, system: str) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        with pytest.raises(ValueError, match="must not be empty"):
            CacheKeys.trading_activity_flag(system=system)

    def test_ttl_is_a_positive_finite_seconds_value(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        ttl = CacheKeys.TTL_TRADING_ACTIVITY_FLAG
        assert isinstance(ttl, int)
        assert ttl > 0
        # Sanity bound: should be hours-to-days, not a forever key.
        assert ttl <= 7 * 24 * 60 * 60


class TestTradingActivitySystemConstants:
    """Subsystem names are typed constants — no stringly-typed callers."""

    def test_exposes_three_subsystem_names(self) -> None:
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS,
            TRADING_ACTIVITY_SYSTEM_PAPER_LIMIT_LIFECYCLE,
            TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
        )

        names = {
            TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS,
            TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
            TRADING_ACTIVITY_SYSTEM_PAPER_LIMIT_LIFECYCLE,
        }
        # All three must be distinct (otherwise pollers would gate on each other);
        # ``paper_brackets`` was removed in Phase 6.4-finalize when the
        # PulsAI-managed bracket sweep was deleted.
        assert len(names) == 3
        for name in names:
            assert isinstance(name, str)
            assert name != ""
            assert name.strip() == name


class TestMarkActive:
    @pytest.mark.asyncio
    async def test_sets_flag_with_configured_ttl(self) -> None:
        from src.infrastructure.cache import trading_activity_flags
        from src.infrastructure.cache.keys import CacheKeys
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS,
        )

        fake_redis = AsyncMock()
        with patch(
            "src.infrastructure.cache.redis_client.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            await trading_activity_flags.mark_active(TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS)

        fake_redis.set.assert_awaited_once_with(
            CacheKeys.trading_activity_flag(system=TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS),
            "1",
            ex=CacheKeys.TTL_TRADING_ACTIVITY_FLAG,
        )

    @pytest.mark.asyncio
    async def test_fails_open_on_redis_error(self) -> None:
        from src.infrastructure.cache import trading_activity_flags
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS,
        )

        fake_redis = AsyncMock()
        fake_redis.set.side_effect = RuntimeError("redis down")
        with patch(
            "src.infrastructure.cache.redis_client.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            # Must not raise — task should proceed with full work as a safe fallback.
            await trading_activity_flags.mark_active(TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS)


class TestHasActive:
    @pytest.mark.asyncio
    async def test_returns_true_when_flag_present(self) -> None:
        from src.infrastructure.cache import trading_activity_flags
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
        )

        fake_redis = AsyncMock()
        fake_redis.exists.return_value = 1
        with patch(
            "src.infrastructure.cache.redis_client.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            result = await trading_activity_flags.has_active(TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_flag_absent(self) -> None:
        from src.infrastructure.cache import trading_activity_flags
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
        )

        fake_redis = AsyncMock()
        fake_redis.exists.return_value = 0
        with patch(
            "src.infrastructure.cache.redis_client.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            result = await trading_activity_flags.has_active(TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS)

        assert result is False

    @pytest.mark.asyncio
    async def test_fails_open_returns_true_on_redis_error(self) -> None:
        """If Redis is unreachable, callers should NOT skip the poll —
        treat the gate as 'unknown → assume work present' so we never silently
        drop user-visible reconciliation."""
        from src.infrastructure.cache import trading_activity_flags
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
        )

        fake_redis = AsyncMock()
        fake_redis.exists.side_effect = RuntimeError("redis down")
        with patch(
            "src.infrastructure.cache.redis_client.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            result = await trading_activity_flags.has_active(TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS)

        assert result is True


class TestClearActive:
    @pytest.mark.asyncio
    async def test_deletes_flag(self) -> None:
        from src.infrastructure.cache import trading_activity_flags
        from src.infrastructure.cache.keys import CacheKeys
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
        )

        fake_redis = AsyncMock()
        with patch(
            "src.infrastructure.cache.redis_client.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            await trading_activity_flags.clear_active(
                TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
            )

        fake_redis.delete.assert_awaited_once_with(
            CacheKeys.trading_activity_flag(system=TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS),
        )

    @pytest.mark.asyncio
    async def test_fails_open_on_redis_error(self) -> None:
        from src.infrastructure.cache import trading_activity_flags
        from src.shared.constants.trading_activity_flags import (
            TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
        )

        fake_redis = AsyncMock()
        fake_redis.delete.side_effect = RuntimeError("redis down")
        with patch(
            "src.infrastructure.cache.redis_client.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            await trading_activity_flags.clear_active(
                TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS,
            )
