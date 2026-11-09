"""Tests for the FRED macro-series Redis cache (VIX / DGS10 / DXY).

This cache decouples ``macro_snapshot_tasks`` from FRED upstream, completing
the upstream-rate-budget consolidation started in Slice 1. Behavior contracts:

- Snapshot round-trips through Redis preserving values + nullability.
- Cache miss returns ``None`` (caller decides; consumers do not fall back to FRED).
- Writes use centralized ``CacheKeys`` and ``TTL_FRED_MACRO_SERIES`` (no inline magic).
"""

from __future__ import annotations

import pytest

from src.infrastructure.cache.fred_macro_series_cache import (
    FredMacroSeriesSnapshot,
    get_fred_macro_series,
    set_fred_macro_series,
)
from src.infrastructure.cache.keys import CacheKeys


class _DummyRedis:
    """Minimal stub mirroring ``set_json``/``get_json`` contract."""

    def __init__(self) -> None:
        self.storage: dict[str, object] = {}
        self.last_ex: dict[str, int] = {}

    async def get_json(self, key: str) -> object:
        return self.storage.get(key)

    async def set_json(self, key: str, value: object, ex: int) -> None:
        self.storage[key] = value
        self.last_ex[key] = ex


def _patch_redis(monkeypatch: pytest.MonkeyPatch) -> _DummyRedis:
    redis = _DummyRedis()

    async def _get_redis_client() -> _DummyRedis:
        return redis

    monkeypatch.setattr(
        "src.infrastructure.cache.redis_client.get_redis_client",
        _get_redis_client,
    )
    return redis


@pytest.mark.asyncio
async def test_macro_series_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """C1: snapshot survives Redis round-trip (dict <-> dataclass)."""
    _patch_redis(monkeypatch)
    snap = FredMacroSeriesSnapshot(
        vix_close=19.4,
        treasury_10y=4.31,
        dxy_close=104.8,
        updated_at="2026-05-31T20:00:00+00:00",
    )
    await set_fred_macro_series(snap)
    loaded = await get_fred_macro_series()
    assert loaded == snap


@pytest.mark.asyncio
async def test_get_macro_series_returns_none_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2: cache miss -> ``None``. Consumers MUST NOT fall back to FRED."""
    _patch_redis(monkeypatch)
    assert await get_fred_macro_series() is None


@pytest.mark.asyncio
async def test_macro_series_uses_centralized_key_and_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3: write goes to ``CacheKeys.fred_macro_series()`` with ``TTL_FRED_MACRO_SERIES``."""
    redis = _patch_redis(monkeypatch)
    snap = FredMacroSeriesSnapshot(
        vix_close=None,
        treasury_10y=None,
        dxy_close=None,
        updated_at="2026-05-31T20:00:00+00:00",
    )
    await set_fred_macro_series(snap)

    key = CacheKeys.fred_macro_series()
    assert key in redis.storage
    assert redis.last_ex[key] == CacheKeys.TTL_FRED_MACRO_SERIES


def test_macro_series_from_dict_handles_partial_payload() -> None:
    """Fail-secure: a partial payload becomes a snapshot with None for missing fields."""
    raw = {"vix_close": 19.0, "updated_at": "2026-05-31T20:00:00+00:00"}
    snap = FredMacroSeriesSnapshot.from_dict(raw)
    assert snap.vix_close == 19.0
    assert snap.treasury_10y is None
    assert snap.dxy_close is None
