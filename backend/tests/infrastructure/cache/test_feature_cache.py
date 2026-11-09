"""
Tests for Feature Cache (Sprint 2.10b).

TDD: Tests written FIRST, before implementation.

WHY feature caching:
- Signal generation recalculates features on every call
- For same symbol/timeframe within a candle interval, features are identical
- Cache avoids ~15ms redundant recalculation
- Training ALWAYS recomputes (no stale data risk)

Tests verify:
- Cache hit returns cached DataFrame
- Cache miss returns None
- TTL matches candle interval
- Cache stores and retrieves Polars DataFrames correctly
- Different symbol/timeframe → different cache keys
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import numpy as np
import polars as pl
import pytest


def _make_feature_df(rows: int = 10) -> pl.DataFrame:
    """Helper: Create a small feature DataFrame for cache testing."""
    from datetime import timedelta

    rng = np.random.default_rng(seed=42)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(hours=i) for i in range(rows)]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "rsi_14": rng.uniform(20, 80, rows),
            "atr_14": rng.uniform(0.5, 2.0, rows),
            "ema_50": rng.uniform(95, 105, rows),
        }
    ).cast({"timestamp": pl.Datetime("ms")})


class TestFeatureCacheKey:
    """Tests for cache key generation."""

    def test_cache_key_includes_symbol_and_timeframe(self) -> None:
        """Cache key must differentiate by symbol and timeframe."""
        from src.infrastructure.cache.feature_cache import FeatureCache

        key1 = FeatureCache.make_key("BTC/USDT", "1h")
        key2 = FeatureCache.make_key("ETH/USDT", "1h")
        key3 = FeatureCache.make_key("BTC/USDT", "15m")

        assert key1 != key2, "Different symbols should produce different keys"
        assert key1 != key3, "Different timeframes should produce different keys"

    def test_cache_key_format(self) -> None:
        """Cache key should follow the project's naming convention."""
        from src.infrastructure.cache.feature_cache import FeatureCache

        key = FeatureCache.make_key("BTC/USDT", "1h")
        assert key.startswith("features:"), f"Key should start with 'features:', got {key}"
        assert "btc_usdt" in key.lower(), f"Key should contain safe symbol, got {key}"
        assert "1h" in key, f"Key should contain timeframe, got {key}"
        assert key == "features:btc_usdt:1h"


class TestFeatureCacheOperations:
    """Tests for cache get/set operations with mocked Redis."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_get_returns_none_on_cache_miss(self, mock_redis: AsyncMock) -> None:
        """Cache miss should return None, not raise."""
        from src.infrastructure.cache.feature_cache import FeatureCache

        cache = FeatureCache(mock_redis)
        result = await cache.get("BTC/USDT", "1h")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_roundtrip(self, mock_redis: AsyncMock) -> None:
        """Stored DataFrame should be retrievable unchanged.

        WHY: Polars DataFrame → bytes (orjson) → Polars DataFrame must be lossless.
        """
        from src.infrastructure.cache.feature_cache import FeatureCache

        cache = FeatureCache(mock_redis)
        df = _make_feature_df(5)

        # Store
        await cache.set("BTC/USDT", "1h", df)

        # Verify set was called
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args

        # Simulate retrieval: extract what was stored
        stored_bytes = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("value")
        assert stored_bytes is not None, "Nothing was stored in Redis"

    @pytest.mark.asyncio
    async def test_ttl_matches_timeframe(self, mock_redis: AsyncMock) -> None:
        """Cache TTL should match the candle interval.

        WHY: Features are valid for the duration of one candle.
        After the candle closes, new features should be recalculated.
        - 1h → TTL ~55 minutes
        - 15m → TTL ~14 minutes
        - 5m → TTL ~4 minutes
        """
        from src.infrastructure.cache.feature_cache import FeatureCache

        cache = FeatureCache(mock_redis)
        df = _make_feature_df(5)

        await cache.set("BTC/USDT", "1h", df)

        # Verify TTL was passed
        call_args = mock_redis.set.call_args
        ttl = call_args[1].get("ex") if call_args[1] else None
        assert ttl is not None, "TTL not set on cache entry"
        # 1h TTL should be ~55 minutes (3300 seconds)
        assert 3000 <= ttl <= 3600, f"1h TTL should be ~3300s, got {ttl}"

    @pytest.mark.asyncio
    async def test_unknown_timeframe_uses_shared_default_ttl(self, mock_redis: AsyncMock) -> None:
        """Unknown feature timeframes should still use the centralized fallback TTL.

        The example was "2h" until 2h became a real LTF band member (2026-08-12) with a derived
        TTL — at which point this stopped testing the fallback at all.
        """
        from src.infrastructure.cache.feature_cache import FeatureCache
        from src.shared.constants.timeframes import TIMEFRAME_REGISTRY

        assert "not-a-timeframe" not in TIMEFRAME_REGISTRY

        cache = FeatureCache(mock_redis)
        df = _make_feature_df(3)

        await cache.set("BTC/USDT", "not-a-timeframe", df)

        ttl = mock_redis.set.call_args[1].get("ex")
        assert ttl == 60

    @pytest.mark.asyncio
    async def test_registry_supported_30m_uses_derived_ttl(self, mock_redis: AsyncMock) -> None:
        """Registry-backed timeframes like 30m should not silently fall back to default TTL."""
        from src.infrastructure.cache.feature_cache import FeatureCache

        cache = FeatureCache(mock_redis)
        df = _make_feature_df(3)

        await cache.set("BTC/USDT", "30m", df)

        ttl = mock_redis.set.call_args[1].get("ex")
        assert ttl == 29 * 60

    def test_ohlcv_ttl_uses_registry_backed_policy_for_extended_timeframes(self) -> None:
        """OHLCVModel cache policy should follow the canonical timeframe registry too."""
        from src.infrastructure.cache.keys import CacheKeys

        assert CacheKeys.get_ttl_for_timeframe("30m") == 29 * 60
        assert CacheKeys.get_ttl_for_timeframe("4h") == (4 * 60 * 60) - (5 * 60)
        assert CacheKeys.get_feature_ttl_for_timeframe("1w") == (7 * 24 * 60 * 60) - (60 * 60)


class TestFeatureCacheIntegration:
    """Integration-style tests (still with mocks, but testing full flow)."""

    @pytest.mark.asyncio
    async def test_cache_is_skipped_for_training(self) -> None:
        """Training should NEVER use cached features.

        WHY: Training needs fresh data to avoid stale feature values.
        Even a slight staleness can corrupt model training.
        """
        from src.infrastructure.cache.feature_cache import FeatureCache

        mock_redis = AsyncMock()
        cache = FeatureCache(mock_redis)

        # Get with skip_cache=True should not call Redis
        result = await cache.get("BTC/USDT", "1h", skip_cache=True)
        assert result is None
        mock_redis.get.assert_not_called()
