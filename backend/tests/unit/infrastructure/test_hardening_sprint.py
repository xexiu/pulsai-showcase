"""
Hardening Sprint TDD Tests

Behavior tests for two categories of issues discovered during the
Feb 24 data consistency audit:

1. TIMEZONE GAPS: All datetime parsing MUST go through ensure_utc() or
   parse_datetime_utc() in src/utils/datetime_utils.py. No inline
   `if dt.tzinfo is None: dt = dt.replace(tzinfo=UTC)` copy-paste.

2. OHLCVModel SINGLE SOURCE OF TRUTH: No file may import OHLCVFetcher directly
   for data fetching. All OHLCVModel access goes through OHLCVService.

@see src/utils/datetime_utils.py (shared UTC utilities)
@see tests/unit/infrastructure/test_ohlcv_data_consistency.py (prior fixes)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.utils.datetime_utils import (
    ensure_utc,
    normalize_timestamp_scalar_to_utc,
    parse_datetime_utc,
    polars_timestamp_to_epoch_ms,
    utc_now,
)

# =============================================================================
# Helpers
# =============================================================================


def _find_direct_fetcher_calls(filepath: str) -> list[str]:
    """
    Detect direct OHLCVFetcher data-fetching calls that bypass OHLCVService.

    Importing OHLCVFetcher is FINE when it's injected into OHLCVService
    (that's the correct pattern used by generate_signals.py, backtest_tasks.py).

    What's NOT fine is calling fetcher.fetch_historical() / fetch_latest()
    directly -- that bypasses the 3-tier cache.
    """
    from pathlib import Path

    source = Path(filepath).read_text()
    bypass_patterns = [
        "fetcher.fetch_historical(",
        "fetcher.fetch_latest(",
        "fetcher.fetch_since_timestamp(",
    ]
    found: list[str] = []
    for i, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in bypass_patterns:
            if pattern in stripped:
                found.extend([f"line {i}: {stripped[:80]}"])
    return found


# =============================================================================
# 1. ensure_utc() / parse_datetime_utc() / utc_now() UNIT TESTS
# =============================================================================


class TestUtcNow:
    """Wall-clock helper is UTC-aware (SoT for patchable ``now``)."""

    def test_returns_timezone_aware_utc(self) -> None:
        n = utc_now()
        assert n.tzinfo is not None
        assert n.utcoffset() == timedelta(0)


class TestEnsureUtc:
    """Direct tests for the shared utility that replaces 9 inline duplications."""

    def test_naive_datetime_gets_utc_attached(self) -> None:
        naive = datetime(2026, 2, 24, 8, 0, 0)
        result = ensure_utc(naive)
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(0)
        assert result.hour == 8, "Hour must not shift"

    def test_utc_datetime_passes_through_unchanged(self) -> None:
        aware = datetime(2026, 2, 24, 8, 0, 0, tzinfo=UTC)
        result = ensure_utc(aware)
        assert result is aware, "Already-UTC should return the same object"

    def test_non_utc_aware_datetime_is_converted_to_utc(self) -> None:
        """A non-UTC aware datetime is CONVERTED — same instant, tzinfo=UTC.

        This test asserted the opposite (tzinfo preserved) until 2026-08-07. `ensure_utc`
        deliberately changed on 2026-08-06 to convert aware inputs: passing them through
        left `.hour`/`.day` readers wrong — `edge_book_cache_ttl_seconds` derives a daily
        refresh boundary via `.replace(hour=...)` and landed five hours off on a `+05:00`
        input. The instant is preserved, so no correct call site can break.
        """
        tokyo = ZoneInfo("Asia/Tokyo")
        aware = datetime(2026, 2, 24, 17, 0, 0, tzinfo=tokyo)  # 08:00 UTC
        result = ensure_utc(aware)

        assert result.utcoffset() == timedelta(0), "must be normalized to UTC"
        assert result.hour == 8, "17:00 Tokyo is 08:00 UTC"
        assert result == aware, "the INSTANT must be unchanged"


class TestParseDatetimeUtc:
    """Direct tests for the combined parse + normalize utility."""

    def test_naive_iso_string_becomes_utc(self) -> None:
        result = parse_datetime_utc("2026-02-24T08:00:00")
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(0)
        assert result == datetime(2026, 2, 24, 8, 0, 0, tzinfo=UTC)

    def test_utc_iso_string_preserved(self) -> None:
        result = parse_datetime_utc("2026-02-24T08:00:00+00:00")
        assert result.utcoffset() == timedelta(0)
        assert result == datetime(2026, 2, 24, 8, 0, 0, tzinfo=UTC)

    def test_offset_iso_string_is_converted_to_utc(self) -> None:
        """An offset ISO string normalizes to UTC, keeping the instant (see TestEnsureUtc)."""
        result = parse_datetime_utc("2026-02-24T08:00:00+09:00")

        assert result.utcoffset() == timedelta(0)
        assert result == datetime(2026, 2, 23, 23, 0, 0, tzinfo=UTC)

    def test_date_only_string_becomes_utc_midnight(self) -> None:
        result = parse_datetime_utc("2026-02-24")
        assert result.utcoffset() == timedelta(0)
        assert result.hour == 0

    def test_comparison_with_utc_now_never_raises(self) -> None:
        """The whole point: parsed result must be comparable with utc_now()."""
        result = parse_datetime_utc("2026-02-20T10:00:00")
        diff = utc_now() - result
        assert isinstance(diff, timedelta)


class TestNormalizeTimestampScalarToUtc:
    """Tests for normalize_timestamp_scalar_to_utc (Polars/cache/JSON scalar → datetime)."""

    def test_none_returns_none(self) -> None:
        assert normalize_timestamp_scalar_to_utc(None) is None

    def test_datetime_naive_gets_utc(self) -> None:
        naive = datetime(2026, 2, 24, 8, 0, 0)
        result = normalize_timestamp_scalar_to_utc(naive)
        assert result is not None
        assert result.tzinfo is not None
        assert result.hour == 8

    def test_datetime_utc_passthrough(self) -> None:
        utc_dt = datetime(2026, 2, 24, 8, 0, 0, tzinfo=UTC)
        result = normalize_timestamp_scalar_to_utc(utc_dt)
        assert result == utc_dt

    def test_int_epoch_ms_converted(self) -> None:
        # 2026-02-24 08:00:00 UTC = 1771920000000 ms (approx)
        ms = 1771920000000
        result = normalize_timestamp_scalar_to_utc(ms)
        assert result is not None
        assert result.tzinfo is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 24

    def test_float_epoch_ms_converted(self) -> None:
        ms_float = 1771920000000.0
        result = normalize_timestamp_scalar_to_utc(ms_float)
        assert result is not None
        assert result.tzinfo is not None

    def test_unsupported_type_returns_none(self) -> None:
        assert normalize_timestamp_scalar_to_utc("2026-02-24") is None
        assert normalize_timestamp_scalar_to_utc([]) is None

    def test_to_pydatetime_scalar_gets_utc(self) -> None:
        """Polars/pandas scalar with to_pydatetime() is normalized (e.g. df['timestamp'].max())."""
        naive = datetime(2026, 2, 24, 12, 0, 0)

        class MockPolarsScalar:
            def to_pydatetime(self) -> datetime:
                return naive

        result = normalize_timestamp_scalar_to_utc(MockPolarsScalar())
        assert result is not None
        assert result.tzinfo is not None
        assert result.hour == 12
        assert result.day == 24


class TestPolarsTimestampToEpochMs:
    """
    SoT for Polars/API timestamp scalar → UTC epoch ms (market.py OHLCVModel/chart-indicators).

    BEHAVIOR: Naive datetimes from pl.from_epoch represent UTC. Python's .timestamp()
    treats naive as LOCAL time (-1h on server in Europe/Madrid). We normalize to UTC
    so all TFs show correct candle time (fixes 5m/15m/30m tooltip -1h bug).
    """

    def test_none_returns_zero(self) -> None:
        """None/invalid must not crash; return 0 for JSON safety."""
        assert polars_timestamp_to_epoch_ms(None) == 0

    def test_int_ms_passthrough(self) -> None:
        """Integer epoch ms (e.g. from cache) must be returned unchanged."""
        ms = 1773675900000  # 2026-03-16 15:45:00 UTC
        assert polars_timestamp_to_epoch_ms(ms) == ms

    def test_naive_utc_datetime_returns_correct_epoch_ms(self) -> None:
        """Naive datetime (as from pl.from_epoch) must be interpreted as UTC."""
        # 2026-03-16 15:45:00 UTC = 1773675900 sec
        expected_ms = 1773675900 * 1000
        naive = datetime(2026, 3, 16, 15, 45, 0)
        assert polars_timestamp_to_epoch_ms(naive) == expected_ms

    def test_utc_aware_datetime_returns_correct_epoch_ms(self) -> None:
        """Timezone-aware UTC datetime must serialize to same epoch ms."""
        expected_ms = 1773675900 * 1000
        utc_dt = datetime(2026, 3, 16, 15, 45, 0, tzinfo=UTC)
        assert polars_timestamp_to_epoch_ms(utc_dt) == expected_ms

    def test_non_utc_aware_datetime_converted_to_utc_epoch(self) -> None:
        """Non-UTC aware (e.g. Asia/Tokyo) must yield UTC epoch for that same moment."""
        tokyo = ZoneInfo("Asia/Tokyo")
        # 2026-03-16 15:45 Tokyo = 06:45 UTC same day (Japan UTC+9, no DST)
        tokyo_dt = datetime(2026, 3, 16, 15, 45, 0, tzinfo=tokyo)
        result_ms = polars_timestamp_to_epoch_ms(tokyo_dt)
        from_utc = datetime.fromtimestamp(result_ms / 1000.0, tz=UTC)
        assert from_utc.hour == 6
        assert from_utc.minute == 45
        assert from_utc.year == 2026
        assert from_utc.month == 3
        assert from_utc.day == 16


# =============================================================================
# 2. SERIALIZATION: datetime.now() must always use UTC
# =============================================================================


class TestSerializationTimezone:
    def test_utc_datetime_serializes_correctly(self) -> None:
        from dataclasses import dataclass

        from src.utils.serialization import dataclass_to_dict

        @dataclass
        class Sample:
            ts: datetime

        obj = Sample(ts=datetime(2026, 2, 24, 8, 0, 0, tzinfo=UTC))
        result = dataclass_to_dict(obj)
        assert "2026-02-24" in result["ts"]
        assert "08:00:00" in result["ts"]


# =============================================================================
# 3. OHLCVModel SINGLE SOURCE OF TRUTH: no direct OHLCVFetcher data fetching
#    (importing OHLCVFetcher to inject into OHLCVService is the correct pattern)
# =============================================================================


class TestTrainingChartsUsesOHLCVService:
    """training_charts.py must fetch data through OHLCVService, not raw OHLCVFetcher."""

    def test_no_direct_fetcher_calls(self) -> None:
        bypasses = _find_direct_fetcher_calls("src/api/routes/admin/training_charts.py")
        assert len(bypasses) == 0, f"training_charts.py still calls OHLCVFetcher directly: {bypasses}. Must route through OHLCVService."


class TestRetrainingTriggerUsesOHLCVService:
    """retraining_trigger_service.py must fetch data through OHLCVService."""

    def test_no_direct_fetcher_calls(self) -> None:
        bypasses = _find_direct_fetcher_calls("src/application/services/retraining_trigger_service.py")
        assert len(bypasses) == 0, f"retraining_trigger_service.py still calls OHLCVFetcher directly: {bypasses}. Must route through OHLCVService."


class TestSignalsDepsUsesOHLCVService:
    """signals_deps.py must not bypass OHLCVService with direct fetcher calls."""

    def test_no_direct_fetcher_calls(self) -> None:
        bypasses = _find_direct_fetcher_calls("src/api/v1/endpoints/signals_deps.py")
        assert len(bypasses) == 0, f"signals_deps.py still calls OHLCVFetcher directly: {bypasses}. Must route through OHLCVService."
