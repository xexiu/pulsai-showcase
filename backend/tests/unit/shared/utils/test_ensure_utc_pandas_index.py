"""Behavior tests for UTC-aware pandas DatetimeIndex normalization."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from src.shared.utils.datetime_utils import ensure_utc_pandas_index


def test_ensure_utc_pandas_index_localizes_naive_as_utc() -> None:
    naive = pd.DatetimeIndex([datetime(2026, 7, 1), datetime(2026, 7, 2)])

    out = ensure_utc_pandas_index(naive)

    assert out.tz is not None
    assert str(out.tz) == "UTC"
    assert out[0] == pd.Timestamp("2026-07-01", tz="UTC")


def test_ensure_utc_pandas_index_converts_aware_to_utc() -> None:
    aware = pd.DatetimeIndex([pd.Timestamp("2026-07-01T02:00:00+02:00"), pd.Timestamp("2026-07-02T02:00:00+02:00")])

    out = ensure_utc_pandas_index(aware)

    assert out[0] == pd.Timestamp("2026-07-01T00:00:00", tz="UTC")


def test_ensure_utc_pandas_index_is_idempotent_on_utc() -> None:
    utc_idx = pd.DatetimeIndex([datetime(2026, 7, 1, tzinfo=UTC)])

    out = ensure_utc_pandas_index(utc_idx)

    assert out.equals(utc_idx)
