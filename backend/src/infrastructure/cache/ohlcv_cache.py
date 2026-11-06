"""
OHLCV Data Cache

Specialized caching for OHLCV (candlestick) data with Polars DataFrame support.
Optimized for the ML pipeline's < 2ms cache lookup requirement.

@see docs/02-technical/DATA_PROCESSING.md - Caching Strategy
@see docs/02-technical/TECH_STACK.md - Redis Configuration
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

import orjson
import polars as pl
from redis.exceptions import RedisError

from src.infrastructure.cache.keys import CacheKeys
from src.shared.constants.ohlcv_columns import OHLCV_CHART_DISPLAY_COLUMNS
from src.shared.utils.ohlcv_frame import ensure_timestamp_datetime
from src.utils.datetime_utils import normalize_timestamp_scalar_to_utc

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.infrastructure.cache.redis_client import RedisClient

logger = logging.getLogger(__name__)


class OHLCVCache:
    """
    OHLCV data cache with Polars DataFrame support.

    This class provides efficient caching of OHLCV data for the ML pipeline.
    Uses orjson for fast serialization and Polars for DataFrame operations.

    Performance Target: < 2ms for cache operations

    Example:
        cache = OHLCVCache(redis_client)

        # Store OHLCV data
        await cache.set("BTC/USDT", "1h", df)

        # Retrieve OHLCV data
        df = await cache.get("BTC/USDT", "1h")
    """

    # Expected columns for OHLCV data. SoT lives in
    # ``src.shared.constants.ohlcv_columns.OHLCV_CHART_DISPLAY_COLUMNS`` —
    # this class attribute is kept as a list (the existing call sites
    # use ``set(self.OHLCV_COLUMNS)`` and ``list(cls.OHLCV_COLUMNS)``
    # below, both happy with the immutable tuple but a list is the
    # historical wire-shape, preserved here to avoid invasive call-site
    # churn on a purely-introspective attribute).
    OHLCV_COLUMNS: ClassVar[list[str]] = list(OHLCV_CHART_DISPLAY_COLUMNS)
    # Optional columns preserved on Redis round-trip (Phase 2 supervisor / closed-bar SoT).
    OPTIONAL_SERIALIZED_COLUMNS: tuple[str, ...] = ("is_closed",)

    def __init__(self, redis_client: RedisClient) -> None:
        """
        Initialize OHLCV cache.

        Args:
            redis_client: Initialized Redis client
        """
        self._redis = redis_client

    def _unavailable(self, operation: str, key: str) -> bool:
        """True when the client holds no connection, and the operation must be a neutral no-op.

        Before ``connect()``, after lifespan closed Redis, or in degraded no-Redis mode -- all
        EXPECTED states, so they are a cheap miss at DEBUG, never an ERROR + traceback. Measured
        2026-09-23: every local API reload logged one, for a chart read still in flight when Redis
        closed. A genuine error on a LIVE client still reaches each method's own handler.
        """
        if self._redis.is_connected():
            return False
        logger.debug("OHLCV cache %s skipped for %s: Redis client not connected", operation, key)
        return True

    def _log_failure(self, message: str, key: str, exc: RedisError) -> None:
        """ERROR + traceback for a failure on a LIVE client; DEBUG when Redis was closed mid-call.

        `_unavailable` runs BEFORE the await, so a lifespan close landing DURING it slips past:
        measured 4 of 4 'Connection closed by server' / 'Error UNKNOWN while writing to socket'
        ERRORs in pulsai.log (2026-09-28..10-01), each inside the API's shutdown. `RedisClient.close`
        drops its handle before awaiting the disconnect, so the client already reads not-connected.
        """
        if self._redis.is_connected():
            logger.exception(message, key, exc)
            return
        logger.debug("OHLCV cache call for %s interrupted by Redis teardown: %s", key, exc)

    @classmethod
    def _columns_to_serialize(cls, df: pl.DataFrame) -> list[str]:
        """Return column order for JSON persistence (core OHLCV + optional flags)."""
        cols = list(cls.OHLCV_COLUMNS)
        for name in cls.OPTIONAL_SERIALIZED_COLUMNS:
            if name in df.columns and name not in cols:
                cols.append(name)
        return cols

    async def get(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> pl.DataFrame | None:
        """
        Get cached OHLCV data as a Polars DataFrame.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            limit: Max number of candles to return (from most recent)

        Returns:
            Polars DataFrame with OHLCV columns, or None if cache miss
        """
        key = CacheKeys.ohlcv(symbol, timeframe)
        if self._unavailable("get", key):
            return None

        try:
            data = await self._redis.get(key)
            if data is None:
                logger.debug("Cache miss for %s", key)
                return None

            # Parse JSON to list of records
            records = orjson.loads(data)

            if not records:
                return None

            # Convert to Polars DataFrame
            df = pl.DataFrame(records)

            # Convert timestamp to datetime if stored as int (SoT helper, idempotent)
            df = ensure_timestamp_datetime(df)

            # Apply limit (most recent candles)
            if limit is not None and len(df) > limit:
                df = df.tail(limit)

            logger.debug("Cache hit for %s: %d candles", key, len(df))
            return df

        except orjson.JSONDecodeError as e:
            logger.warning("Failed to decode OHLCV cache for %s: %s", key, e)
            return None
        except RedisError as e:
            self._log_failure("Error reading OHLCV cache for %s: %s", key, e)
            return None
        except Exception as e:
            logger.exception("Error reading OHLCV cache for %s: %s", key, e)
            return None

    async def set(
        self,
        symbol: str,
        timeframe: str,
        df: pl.DataFrame,
        ttl: int | None = None,
    ) -> bool:
        """
        Cache OHLCV data from a Polars DataFrame.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            df: Polars DataFrame with OHLCV columns
            ttl: Cache TTL in seconds (default: auto-calculated from timeframe)

        Returns:
            True if successful, False otherwise
        """
        key = CacheKeys.ohlcv(symbol, timeframe)
        if self._unavailable("set", key):
            return False

        # Auto-calculate TTL if not provided
        if ttl is None:
            ttl = CacheKeys.get_ttl_for_timeframe(timeframe)

        try:
            # Validate required columns
            missing_cols = set(self.OHLCV_COLUMNS) - set(df.columns)
            if missing_cols:
                logger.warning("Missing OHLCV columns: %s", missing_cols)
                return False

            # Convert datetime to epoch ms for JSON serialization
            df_serializable = df.select(self._columns_to_serialize(df))

            if df_serializable["timestamp"].dtype == pl.Datetime:
                df_serializable = df_serializable.with_columns((pl.col("timestamp").dt.epoch("ms")).alias("timestamp"))

            # Convert to list of records
            records = df_serializable.to_dicts()

            # Serialize with orjson
            json_bytes = orjson.dumps(records)

            # Store in Redis
            result = await self._redis.set(key, json_bytes, ex=ttl)

            if result:
                logger.debug(
                    "Cached %d candles for %s (TTL: %ds)",
                    len(df),
                    key,
                    ttl,
                )

            return result

        except RedisError as e:
            self._log_failure("Failed to cache OHLCV for %s: %s", key, e)
            return False
        except Exception as e:
            logger.exception("Failed to cache OHLCV for %s: %s", key, e)
            return False

    async def _with_ohlcv_cache_lock(
        self,
        symbol: str,
        timeframe: str,
        op: Callable[[], Awaitable[bool]],
    ) -> bool:
        """
        Serialize concurrent cache mutations with a Redis distributed lock.

        WHY: OHLCVCache.append() and update_last_candle() do a non-atomic
        read-modify-write (GET -> merge -> SET). Without a lock, concurrent
        writers can overwrite each other's updates.
        """
        lock_key = CacheKeys.ohlcv_lock(symbol, timeframe)
        blocking_timeout = CacheKeys.OHLCV_CACHE_LOCK_BLOCKING_TIMEOUT_SECONDS
        lock = self._redis.client.lock(
            lock_key,
            timeout=CacheKeys.OHLCV_CACHE_LOCK_TIMEOUT_SECONDS,
            blocking=True,
            blocking_timeout=blocking_timeout,
        )

        acquired = await lock.acquire()
        if not acquired:
            logger.warning(
                "OHLCV cache lock busy; refusing mutation for %s %s",
                symbol,
                timeframe,
            )
            return False

        try:
            return await op()
        finally:
            try:
                await lock.release()
            except (RedisError, RuntimeError, OSError) as exc:  # lock lost/expired, client closed, socket gone
                logger.debug(
                    "Failed to release OHLCV cache lock for %s %s: %s",
                    symbol,
                    timeframe,
                    exc,
                )

    async def append(
        self,
        symbol: str,
        timeframe: str,
        new_candle: dict[str, Any],
    ) -> bool:
        """
        Append a new candle to cached OHLCV data.

        Efficient for real-time updates without full cache refresh.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            new_candle: Dict with OHLCV fields

        Returns:
            True if successful, False otherwise
        """

        if self._unavailable("append", CacheKeys.ohlcv(symbol, timeframe)):
            return False

        async def _do_append() -> bool:
            # Get existing data
            existing_df = await self.get(symbol, timeframe)

            if existing_df is None:
                # No existing data, create new DataFrame
                new_df = pl.DataFrame([new_candle])
            else:
                # Append new candle
                new_row = pl.DataFrame([new_candle])

                # Ensure timestamp format matches
                if "timestamp" in new_row.columns and isinstance(new_candle["timestamp"], datetime):
                    # Match Polars time-unit from existing_df (usually 'us')
                    # to avoid concat schema errors.
                    target_dtype = existing_df["timestamp"].dtype
                    new_row = new_row.with_columns(
                        pl.col("timestamp").cast(target_dtype),
                    )

                # Concat and deduplicate by timestamp
                new_df = pl.concat([existing_df, new_row])
                new_df = new_df.unique(subset=["timestamp"], keep="last")
                new_df = new_df.sort("timestamp")

            return await self.set(symbol, timeframe, new_df)

        return await self._with_ohlcv_cache_lock(symbol, timeframe, _do_append)

    async def update_last_candle(
        self,
        symbol: str,
        timeframe: str,
        updated_candle: dict[str, Any],
    ) -> bool:
        """
        Update the last (incomplete) candle in cached data.

        Used for real-time candle updates before close.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            updated_candle: Dict with updated OHLCV fields

        Returns:
            True if successful, False otherwise
        """

        if self._unavailable("update_last_candle", CacheKeys.ohlcv(symbol, timeframe)):
            return False

        async def _do_update_last_candle() -> bool:
            existing_df = await self.get(symbol, timeframe)

            if existing_df is None or len(existing_df) == 0:
                return False

            # Replace last row
            all_but_last = existing_df.head(len(existing_df) - 1)
            new_row = pl.DataFrame([updated_candle])

            # Guard: cast only when timestamp is present AND already a datetime
            # (match existing_df time-unit, usually 'us', to avoid concat errors).
            if "timestamp" in new_row.columns and isinstance(updated_candle["timestamp"], datetime):
                target_dtype = existing_df["timestamp"].dtype
                new_row = new_row.with_columns(
                    pl.col("timestamp").cast(target_dtype),
                )

            new_df = pl.concat([all_but_last, new_row])

            return await self.set(symbol, timeframe, new_df)

        return await self._with_ohlcv_cache_lock(
            symbol,
            timeframe,
            _do_update_last_candle,
        )

    async def delete(self, symbol: str, timeframe: str) -> bool:
        """
        Delete cached OHLCV data.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")

        Returns:
            True if key was deleted, False if key didn't exist
        """
        key = CacheKeys.ohlcv(symbol, timeframe)
        if self._unavailable("delete", key):
            return False
        result = await self._redis.delete(key)
        return result > 0

    async def get_last_timestamp(
        self,
        symbol: str,
        timeframe: str,
    ) -> datetime | None:
        """
        Get the timestamp of the last cached candle.

        Useful for determining what data needs to be fetched.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")

        Returns:
            Datetime of last candle, or None if no data cached
        """
        df = await self.get(symbol, timeframe, limit=1)

        if df is None or len(df) == 0:
            return None

        last_ts = df["timestamp"][-1]

        return normalize_timestamp_scalar_to_utc(last_ts)

    async def get_candle_count(self, symbol: str, timeframe: str) -> int:
        """
        Get the number of cached candles.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")

        Returns:
            Number of cached candles, or 0 if no data
        """
        key = CacheKeys.ohlcv(symbol, timeframe)
        if self._unavailable("get_candle_count", key):
            return 0
        data = await self._redis.get(key)

        if data is None:
            return 0

        try:
            records = orjson.loads(data)
            return len(records)
        except orjson.JSONDecodeError:
            return 0
