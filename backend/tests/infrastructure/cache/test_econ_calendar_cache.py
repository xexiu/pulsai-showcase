"""Tests for EconScheduleSnapshot + FredObservationsSnapshot Redis caches.

Behavior-focused: alert tasks (per-minute beat) MUST read these caches instead
of hitting FRED directly. These tests pin the contract that:
- Round-trip preserves data (dataclass <-> dict <-> Redis).
- Cache miss returns ``None`` (caller decides; no upstream call).
- Write uses centralized CacheKeys and TTLs (no inline magic values).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.infrastructure.cache.econ_calendar_cache import (
    EconScheduleSnapshot,
    FredObservationsSnapshot,
    get_econ_schedule,
    get_fred_observations,
    set_econ_schedule,
    set_fred_observations,
)
from src.infrastructure.cache.keys import CacheKeys


class _DummyRedis:
    """Minimal stub mirroring the contract used by infra cache modules."""

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


# ----------------------- EconScheduleSnapshot ------------------------------


@pytest.mark.asyncio
async def test_econ_schedule_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """C1: snapshot survives Redis round-trip (dict <-> dataclass)."""
    _patch_redis(monkeypatch)
    fomc_a = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
    cpi_a = datetime(2026, 7, 11, 12, 30, tzinfo=UTC)
    nfp_a = datetime(2026, 8, 1, 12, 30, tzinfo=UTC)

    snap = EconScheduleSnapshot(
        fomc=(fomc_a,),
        cpi=(cpi_a,),
        nfp=(nfp_a,),
        updated_at="2026-05-31T20:00:00+00:00",
    )
    await set_econ_schedule(snap)
    loaded = await get_econ_schedule()
    assert loaded == snap


@pytest.mark.asyncio
async def test_get_econ_schedule_returns_none_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """C3: cache miss -> ``None``. Caller MUST NOT fall back to FRED."""
    _patch_redis(monkeypatch)
    assert await get_econ_schedule() is None


@pytest.mark.asyncio
async def test_econ_schedule_uses_centralized_key_and_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """SoT: write goes to ``CacheKeys.econ_schedule()`` with ``TTL_ECON_SCHEDULE``."""
    redis = _patch_redis(monkeypatch)
    snap = EconScheduleSnapshot(
        fomc=(),
        cpi=(),
        nfp=(),
        updated_at="2026-05-31T20:00:00+00:00",
    )
    await set_econ_schedule(snap)

    key = CacheKeys.econ_schedule()
    assert key in redis.storage
    assert redis.last_ex[key] == CacheKeys.TTL_ECON_SCHEDULE


@pytest.mark.asyncio
async def test_econ_schedule_from_dict_skips_invalid_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-secure: corrupt entries are dropped, not raised."""
    _patch_redis(monkeypatch)
    valid_iso = "2026-07-30T18:00:00+00:00"
    raw = {
        "fomc": [valid_iso, "not-a-timestamp"],
        "cpi": [],
        "nfp": [],
        "updated_at": "2026-05-31T20:00:00+00:00",
    }
    snap = EconScheduleSnapshot.from_dict(raw)
    assert len(snap.fomc) == 1
    assert snap.fomc[0] == datetime(2026, 7, 30, 18, 0, tzinfo=UTC)


# --------------------- FredObservationsSnapshot ----------------------------


@pytest.mark.asyncio
async def test_fred_observations_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """C2: observation pairs survive Redis round-trip."""
    _patch_redis(monkeypatch)
    from datetime import date

    snap = FredObservationsSnapshot(
        cpi_pair=((date(2026, 4, 1), 313.5), (date(2026, 3, 1), 312.4)),
        nfp_pair=((date(2026, 4, 1), 158_000.0), (date(2026, 3, 1), 157_700.0)),
        fed_funds_pair=((date(2026, 5, 1), 5.5), (date(2026, 4, 1), 5.5)),
        updated_at="2026-05-31T20:00:00+00:00",
    )
    await set_fred_observations(snap)
    loaded = await get_fred_observations()
    assert loaded == snap


@pytest.mark.asyncio
async def test_get_fred_observations_returns_none_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3: cache miss -> ``None``."""
    _patch_redis(monkeypatch)
    assert await get_fred_observations() is None


@pytest.mark.asyncio
async def test_fred_observations_uses_centralized_key_and_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SoT: write goes to ``CacheKeys.fred_observations()`` with ``TTL_FRED_OBSERVATIONS``."""
    redis = _patch_redis(monkeypatch)
    snap = FredObservationsSnapshot(
        cpi_pair=(),
        nfp_pair=(),
        fed_funds_pair=(),
        updated_at="2026-05-31T20:00:00+00:00",
    )
    await set_fred_observations(snap)

    key = CacheKeys.fred_observations()
    assert key in redis.storage
    assert redis.last_ex[key] == CacheKeys.TTL_FRED_OBSERVATIONS


def test_fred_observations_to_pairs_helper() -> None:
    """Helper exposes obs pairs as list[(date, float)] for ``compute_econ_features_at``."""
    from datetime import date

    snap = FredObservationsSnapshot(
        cpi_pair=((date(2026, 4, 1), 313.5), (date(2026, 3, 1), 312.4)),
        nfp_pair=(),
        fed_funds_pair=(),
        updated_at="2026-05-31T20:00:00+00:00",
    )
    pairs = snap.cpi_as_list()
    assert pairs == [(date(2026, 4, 1), 313.5), (date(2026, 3, 1), 312.4)]
