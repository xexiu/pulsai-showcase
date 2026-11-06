"""Unit tests for the OHLCV-frame timestamp normalization SoT helper.

Covers ``ensure_timestamp_datetime`` — the idempotent epoch-ms ``Int64`` →
``Datetime`` cast that was previously inlined at 4 OHLCV call sites
(tier-access reader, historical fetcher, Redis cache reader, supervisor
precompute writer). The behavior asserted here is the contract those call
sites depend on.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from src.shared.utils.ohlcv_frame import ensure_timestamp_datetime

# 2023-11-14T22:13:20Z — a fixed epoch-ms instant for exact value assertions.
_EPOCH_MS = 1_700_000_000_000
_EXPECTED_DT = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def test_int64_epoch_ms_is_cast_to_datetime() -> None:
    """An Int64 ``timestamp`` column is converted to a Polars Datetime."""
    df = pl.DataFrame({"timestamp": [_EPOCH_MS], "close": [1.0]})
    assert df["timestamp"].dtype == pl.Int64

    out = ensure_timestamp_datetime(df)

    assert out["timestamp"].dtype == pl.Datetime
    # Other columns are untouched.
    assert out["close"].to_list() == [1.0]


def test_uint64_epoch_ms_is_cast_to_datetime() -> None:
    """UInt64 epoch-ms (Polars inference / unsigned wire values) must still decode.

    Regression: ``dtype == pl.Int64`` skipped UInt64; ``.dt.weekday()`` then failed
    on integer columns during chart-indicators supervisor precompute.
    """
    df = pl.DataFrame({"timestamp": pl.Series([_EPOCH_MS], dtype=pl.UInt64)})

    out = ensure_timestamp_datetime(df)

    assert out["timestamp"].dtype == pl.Datetime
    assert out["timestamp"].to_list()[0] == _EXPECTED_DT.replace(tzinfo=None)


def test_int64_epoch_ms_value_is_correct() -> None:
    """The cast decodes epoch-milliseconds to the exact UTC instant."""
    df = pl.DataFrame({"timestamp": [_EPOCH_MS]})

    out = ensure_timestamp_datetime(df)

    # Polars-naive Datetime compared against the same wall-clock instant.
    assert out["timestamp"].to_list()[0] == _EXPECTED_DT.replace(tzinfo=None)


def test_already_datetime_is_unchanged() -> None:
    """A frame whose timestamp is already Datetime is returned untouched (no-op)."""
    naive = _EXPECTED_DT.replace(tzinfo=None)
    df = pl.DataFrame({"timestamp": [naive], "close": [2.0]})
    assert df["timestamp"].dtype == pl.Datetime

    out = ensure_timestamp_datetime(df)

    assert out["timestamp"].dtype == pl.Datetime
    assert out["timestamp"].to_list() == [naive]
    assert out["close"].to_list() == [2.0]


def test_missing_timestamp_column_is_noop() -> None:
    """A frame without a ``timestamp`` column passes through unmodified."""
    df = pl.DataFrame({"open": [1.0], "close": [2.0]})

    out = ensure_timestamp_datetime(df)

    assert out.columns == ["open", "close"]
    assert out["open"].to_list() == [1.0]
    assert out["close"].to_list() == [2.0]


def test_custom_column_name_is_honored() -> None:
    """The ``column`` kwarg targets a non-default timestamp column."""
    df = pl.DataFrame({"open_time": [_EPOCH_MS]})

    out = ensure_timestamp_datetime(df, column="open_time")

    assert out["open_time"].dtype == pl.Datetime
    assert out["open_time"].to_list()[0] == _EXPECTED_DT.replace(tzinfo=None)


def test_idempotent_double_application() -> None:
    """Applying the cast twice yields the same result as once (idempotent)."""
    df = pl.DataFrame({"timestamp": [_EPOCH_MS]})

    once = ensure_timestamp_datetime(df)
    twice = ensure_timestamp_datetime(once)

    assert twice["timestamp"].dtype == pl.Datetime
    assert twice["timestamp"].to_list() == once["timestamp"].to_list()
