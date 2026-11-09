"""
Regression tests for OHLCVCache concurrent mutation safety.

These tests focus on the classic TOCTOU pattern inside OHLCVCache.append()
and update_last_candle(): GET -> merge -> SET.

Without a Redis lock, concurrent writers can overwrite each other's updates
and lose candles.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import polars as pl
import pytest

from src.infrastructure.cache.ohlcv_cache import OHLCVCache


class _FakeRedisAsyncLock:
    def __init__(self, lock: asyncio.Lock) -> None:
        self._lock = lock

    async def acquire(self) -> bool:
        await self._lock.acquire()
        return True

    async def release(self) -> None:
        self._lock.release()


class _FakeRedisAsyncClient:
    def __init__(self, global_locks: dict[str, asyncio.Lock]) -> None:
        self._global_locks = global_locks

    def lock(self, name: str, **_: Any) -> _FakeRedisAsyncLock:
        lock = self._global_locks.setdefault(name, asyncio.Lock())
        return _FakeRedisAsyncLock(lock)


class FakeRedisClientWrapper:
    """
    Minimal RedisClient wrapper implementation for OHLCVCache unit tests.

    Uses an in-memory dict as storage and an asyncio.Lock as a stand-in for
    redis-py's async lock API.
    """

    def __init__(self, *, get_delay_sec: float = 0.02) -> None:
        self._store: dict[str, bytes] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._client = _FakeRedisAsyncClient(self._locks)
        self._get_delay_sec = get_delay_sec

    def is_connected(self) -> bool:
        return True

    @property
    def client(self) -> _FakeRedisAsyncClient:
        return self._client

    async def get(self, key: str) -> bytes | None:
        await asyncio.sleep(self._get_delay_sec)
        return self._store.get(key)

    async def set(self, key: str, value: bytes | str, ex: int | None = None) -> bool:
        _ = ex
        # Yield so concurrent tasks can interleave without the distributed lock.
        await asyncio.sleep(0)
        if isinstance(value, str):
            value = value.encode("utf-8")
        self._store[key] = value
        return True


def _make_ohlcv_row(ts: datetime, i: int) -> dict[str, Any]:
    return {
        "timestamp": ts,
        "open": 100.0 + i,
        "high": 105.0 + i,
        "low": 95.0 + i,
        "close": 102.0 + i,
        "volume": 1000 + i,
    }


@pytest.mark.asyncio
async def test_concurrent_append_does_not_lose_candles() -> None:
    fake_redis = FakeRedisClientWrapper()
    cache = OHLCVCache(fake_redis)  # type: ignore[arg-type]

    symbol = "BTC/USDT"
    timeframe = "1h"

    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 1, 1, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 1, 2, 0, 0, tzinfo=UTC)

    df_init = pl.DataFrame([_make_ohlcv_row(t0, 0)])
    assert await cache.set(symbol, timeframe, df_init) is True

    candle_a = _make_ohlcv_row(t1, 1)
    candle_b = _make_ohlcv_row(t2, 2)

    await asyncio.gather(
        cache.append(symbol, timeframe, candle_a),
        cache.append(symbol, timeframe, candle_b),
    )

    final_df = await cache.get(symbol, timeframe)
    assert final_df is not None
    assert not final_df.is_empty()

    ts_ms = final_df.with_columns(pl.col("timestamp").dt.epoch("ms").alias("ts_ms"))["ts_ms"].to_list()

    assert set(ts_ms) == {
        int(t0.timestamp() * 1000),
        int(t1.timestamp() * 1000),
        int(t2.timestamp() * 1000),
    }


@pytest.mark.asyncio
async def test_update_last_candle_casts_datetime_to_existing_timestamp_dtype() -> None:
    """Datetime candle updates must concat without schema/time-unit mismatch."""
    fake_redis = FakeRedisClientWrapper(get_delay_sec=0.0)
    cache = OHLCVCache(fake_redis)  # type: ignore[arg-type]

    symbol = "BTC/USDT"
    timeframe = "1h"
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 1, 0, 30, 0, tzinfo=UTC)

    assert await cache.set(symbol, timeframe, pl.DataFrame([_make_ohlcv_row(t0, 0)])) is True

    updated = _make_ohlcv_row(t1, 9)
    assert await cache.update_last_candle(symbol, timeframe, updated) is True

    final_df = await cache.get(symbol, timeframe)
    assert final_df is not None
    assert len(final_df) == 1
    assert final_df["close"][0] == pytest.approx(111.0)
    assert final_df["timestamp"].dtype == pl.Datetime
    got_ms = final_df.with_columns(pl.col("timestamp").dt.epoch("ms").alias("ts_ms"))["ts_ms"][0]
    assert got_ms == int(t1.timestamp() * 1000)


@pytest.mark.asyncio
async def test_update_last_candle_rejects_int_timestamp_schema_mismatch() -> None:
    """Int epoch timestamps skip the datetime cast and must not silently concat."""
    fake_redis = FakeRedisClientWrapper(get_delay_sec=0.0)
    cache = OHLCVCache(fake_redis)  # type: ignore[arg-type]

    symbol = "ETH/USDT"
    timeframe = "4h"
    t0 = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)
    assert await cache.set(symbol, timeframe, pl.DataFrame([_make_ohlcv_row(t0, 0)])) is True

    updated = {
        "timestamp": int(t0.timestamp() * 1000),
        "open": 200.0,
        "high": 210.0,
        "low": 190.0,
        "close": 205.0,
        "volume": 50.0,
    }
    with pytest.raises(pl.exceptions.SchemaError):
        await cache.update_last_candle(symbol, timeframe, updated)
