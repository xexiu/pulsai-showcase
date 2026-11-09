"""
Feature Cache — Redis-backed cache for computed feature DataFrames (Sprint 2.10b).

WHY feature caching:
- Signal generation calls FastFeatureCalculator on every request (~15ms)
- For the same symbol/timeframe within one candle interval, features are IDENTICAL
- Caching avoids redundant recalculation, saving ~10-15ms per signal
- TTL matches candle interval (features expire when new candle arrives)

CRITICAL: Training NEVER uses cached features.
- Stale features corrupt model training
- set() and get() both support skip_cache flag

Serialization:
- Uses orjson for Polars DataFrame ↔ bytes conversion
- Stores as JSON (column-oriented) for compact representation

@see docs/02-technical/TECH_STACK.md — Redis Caching Strategy
@see infrastructure/cache/keys.py — CacheKeys.features()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

from src.infrastructure.cache.keys import CacheKeys

if TYPE_CHECKING:
    from src.infrastructure.cache.redis_client import RedisClient

logger = logging.getLogger(__name__)


class FeatureCache:
    """
    Redis-backed cache for computed feature DataFrames.

    Stores Polars DataFrames as JSON in Redis with timeframe-based TTL.
    Supports skip_cache for training and forced refresh scenarios.

    Example:
        cache = FeatureCache(redis_client)

        # Signal generation (uses cache)
        cached = await cache.get("BTC/USDT", "1h")
        if cached is None:
            features = calculator.calculate_all(ohlcv)
            await cache.set("BTC/USDT", "1h", features)
        else:
            features = cached

        # Training (skips cache)
        features = calculator.calculate_all(ohlcv)
        # Don't cache training features
    """

    def __init__(self, redis_client: RedisClient) -> None:
        """
        Initialize feature cache.

        Args:
            redis_client: Async Redis client instance
        """
        self._redis = redis_client

    @staticmethod
    def make_key(symbol: str, timeframe: str) -> str:
        """
        Generate cache key for features.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")

        Returns:
            Cache key like "features:btc_usdt:1h"
        """
        return CacheKeys.features(symbol, timeframe)

    async def get(
        self,
        symbol: str,
        timeframe: str,
        skip_cache: bool = False,
    ) -> pl.DataFrame | None:
        """
        Retrieve cached feature DataFrame.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            skip_cache: If True, always return None (for training)

        Returns:
            Cached Polars DataFrame, or None if miss/skipped
        """
        if skip_cache:
            return None

        key = self.make_key(symbol, timeframe)

        try:
            data = await self._redis.get(key)

            if data is None:
                logger.debug("Feature cache MISS: %s %s", symbol, timeframe)
                return None

            # Deserialize JSON → Polars DataFrame
            import orjson

            json_data = orjson.loads(data)
            df = pl.DataFrame(json_data)

            logger.debug(
                "Feature cache HIT: %s %s (%d rows, %d cols)",
                symbol,
                timeframe,
                len(df),
                len(df.columns),
            )
            return df

        except Exception:
            # Cache failure should NEVER break signal generation
            logger.warning(
                "Feature cache get failed for %s %s — proceeding without cache",
                symbol,
                timeframe,
                exc_info=True,
            )
            return None

    async def set(
        self,
        symbol: str,
        timeframe: str,
        features_df: pl.DataFrame,
    ) -> None:
        """
        Store feature DataFrame in cache.

        TTL is automatically set based on timeframe.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            features_df: Polars DataFrame to cache
        """
        key = self.make_key(symbol, timeframe)
        ttl = CacheKeys.get_feature_ttl_for_timeframe(timeframe)

        try:
            # Serialize Polars DataFrame → JSON bytes
            # Using write_json() for lossless column types, then orjson for speed
            json_str = features_df.write_json()
            json_bytes = json_str.encode("utf-8")

            await self._redis.set(key, json_bytes, ex=ttl)

            logger.debug(
                "Feature cache SET: %s %s (%d rows, TTL=%ds)",
                symbol,
                timeframe,
                len(features_df),
                ttl,
            )

        except Exception:
            # Cache failure should NEVER break signal generation
            logger.warning(
                "Feature cache set failed for %s %s — continuing without cache",
                symbol,
                timeframe,
                exc_info=True,
            )

    async def invalidate(self, symbol: str, timeframe: str) -> None:
        """
        Remove cached features for a symbol/timeframe.

        Call when model is retrained or features config changes.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
        """
        key = self.make_key(symbol, timeframe)
        try:
            await self._redis.delete(key)
            logger.info("Feature cache invalidated: %s %s", symbol, timeframe)
        except Exception:
            logger.warning(
                "Feature cache invalidation failed for %s %s",
                symbol,
                timeframe,
                exc_info=True,
            )
