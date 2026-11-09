"""[t11] Determinism cached-vs-fresh OHLCVModel round-trip (Phase 2 — RED).

WHY:
- Plan 8d8170ab §'Data integrity': the single biggest risk of introducing
  a WS-backed Redis tier is **training/serving skew**. If the Redis
  serialisation drops precision, reorders columns, or loses the new
  `is_closed` flag the supervisor will emit per
  `contracts/ohlcv_stream_candle_v1.contract.json`, models silently see
  different inputs offline vs. online.
- This RED test pins two contracts on the cache round-trip that Phase 2
  MUST satisfy:
    (a) Bit-exact round-trip of OHLC float64 values and timestamps.
    (b) The `is_closed` field emitted by the supervisor is preserved
        through the cache (currently dropped by `OHLCVCache` because
        `OHLCV_COLUMNS` hardcodes only the 6 legacy columns).

Until p2-supervisor extends the cache schema to carry `is_closed`,
assertion (b) will fail → RED. Once implemented, both must hold.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest


def _make_reference_df(n: int = 200) -> pl.DataFrame:
    """Deterministic seed data — values chosen to expose float-precision drift.

    Each row carries `is_closed=True` so we can test the supervisor-emitted
    format round-trips through the cache.
    """
    base = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    return pl.DataFrame(
        {
            "timestamp": [base + timedelta(minutes=5 * i) for i in range(n)],
            "open": [60000.0 + i * 0.123456789 for i in range(n)],
            "high": [60100.0 + i * 0.234567891 for i in range(n)],
            "low": [59900.0 + i * 0.345678912 for i in range(n)],
            "close": [60050.0 + i * 0.456789123 for i in range(n)],
            "volume": [10.0 + i * 0.0001 for i in range(n)],
            "is_closed": [True] * n,
        }
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ohlcv_cache_roundtrip_preserves_float64_bits() -> None:
    """Redis cache MUST round-trip every OHLC float bit-exactly.

    If this ever fails, Redis-tier data no longer matches the REST-tier data
    seen during training → training/serving skew.
    """
    from src.infrastructure.cache.ohlcv_cache import OHLCVCache

    reference = _make_reference_df(200)
    reference_legacy = reference.drop("is_closed")

    stored: dict[str, bytes] = {}

    redis_client = MagicMock()

    async def _fake_set(key: str, value: Any, **_: Any) -> bool:
        stored[key] = value
        return True

    async def _fake_get(key: str) -> Any:
        return stored.get(key)

    redis_client.set = AsyncMock(side_effect=_fake_set)
    redis_client.get = AsyncMock(side_effect=_fake_get)

    cache = OHLCVCache(redis_client)

    await cache.set("BTC/USDT", "5m", reference_legacy)
    got = await cache.get("BTC/USDT", "5m")

    assert got is not None, "Round-trip returned None — cache contract broken."
    # Legacy columns in order — same schema, same dtypes, same float bits.
    assert got.columns[:6] == ["timestamp", "open", "high", "low", "close", "volume"]
    for col in ("open", "high", "low", "close", "volume"):
        src_values = reference_legacy[col].to_list()
        got_values = got[col].to_list()
        for i, (a, b) in enumerate(zip(src_values, got_values, strict=True)):
            assert a == b, f"Redis round-trip drifted on column {col}[{i}]: {a!r} != {b!r}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ohlcv_cache_roundtrip_preserves_is_closed_flag() -> None:
    """Supervisor-emitted is_closed flag MUST survive the Redis round-trip.

    The supervisor per contracts/ohlcv_stream_candle_v1.contract.json emits
    an `is_closed` bool alongside OHLCVModel. Today `OHLCVCache.OHLCV_COLUMNS`
    hardcodes only the 6 legacy columns and will drop `is_closed` on `.set`.

    This test is RED until p2-supervisor extends the cache schema. When
    GREEN, it pins the invariant: a downstream consumer can always tell
    whether a bar is closed from the cached tail alone (no heartbeat
    lookup required to re-derive it).
    """
    from src.infrastructure.cache.ohlcv_cache import OHLCVCache

    reference = _make_reference_df(50)

    stored: dict[str, bytes] = {}

    redis_client = MagicMock()

    async def _fake_set(key: str, value: Any, **_: Any) -> bool:
        stored[key] = value
        return True

    async def _fake_get(key: str) -> Any:
        return stored.get(key)

    redis_client.set = AsyncMock(side_effect=_fake_set)
    redis_client.get = AsyncMock(side_effect=_fake_get)

    cache = OHLCVCache(redis_client)

    await cache.set("BTC/USDT", "5m", reference)
    got = await cache.get("BTC/USDT", "5m")

    assert got is not None, "Cache round-trip dropped the whole tail."
    assert "is_closed" in got.columns, (
        "OHLCVCache dropped the supervisor `is_closed` flag on round-trip. "
        "Phase 2 GREEN (p2-supervisor) MUST extend OHLCVCache so this flag "
        "survives. Without it, inference cannot distinguish forming from "
        "closed bars when reading the cache directly."
    )
    assert got["is_closed"].to_list() == [True] * 50
