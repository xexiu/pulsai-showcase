"""datetime_utils.epoch_ms: pandas times of ANY unit -> UTC epoch milliseconds -- the one home (EPOCH-MS-HOME).

IMPORTERS / CALLERS: none (a test module). AFFECTED API: src/shared/utils/datetime_utils (epoch_ms).
DATA SCHEMAS: none -- synthetic timestamps.

The conversion was re-derived inline at 8 sites (2026-10-12) after feature_cache.epoch_ms named it; the last copy,
LTF-GRID's builder, collapsed every built bar into one. These pin the behaviour every caller relies on.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
import pytest

from src.shared.utils.datetime_utils import epoch_ms

MS = [1_735_689_600_000, 1_735_689_660_000]  # 2025-01-01 00:00 and 00:01 UTC


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_an_index_of_any_unit_reads_as_the_same_milliseconds(unit: Literal["s", "ms", "us", "ns"]) -> None:
    index = pd.DatetimeIndex(pd.to_datetime(MS, unit="ms", utc=True)).as_unit(unit)
    assert epoch_ms(index).tolist() == MS


def test_a_naive_index_is_read_as_utc() -> None:
    naive = pd.DatetimeIndex(["2025-01-01 00:00", "2025-01-01 00:01"])
    assert epoch_ms(naive).tolist() == MS


def test_a_series_of_times_reads_like_an_index() -> None:
    times = pd.Series(pd.to_datetime(MS, unit="ms", utc=True)).dt.as_unit("us")
    assert epoch_ms(times).tolist() == MS


def test_canary_the_old_divide_is_wrong_on_a_millisecond_index() -> None:
    """The copy this replaces assumed nanoseconds; under pandas 3 a millisecond index makes it 1e6 too small."""
    index = pd.DatetimeIndex(pd.to_datetime(MS, unit="ms", utc=True)).as_unit("ms")
    assert (index.asi8 // 1_000_000).tolist() != MS
