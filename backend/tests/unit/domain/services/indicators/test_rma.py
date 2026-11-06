"""Wilder's RMA: one recurrence, its seed rules, and the ATR built on the SMA seed.

IMPORTERS/CALLERS: pytest only. AFFECTED API: pins src/domain/services/indicators/rma (rma_seeded_at, rma_mean_seeded,
rma_sma_seeded, atr_sma_seeded). DATA SCHEMAS: none.

The values are worked by hand on x = 1..6, period 3, so a changed recurrence or a moved seed fails here, not in a model.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.domain.services.indicators.rma import (
    atr_first_seeded,
    atr_simple,
    atr_sma_seeded,
    rma_first_seeded,
    rma_mean_seeded,
    rma_seeded_at,
    rma_sma_seeded,
)
from src.domain.services.indicators.trailing import trailing_mean
from src.domain.services.indicators.true_range import true_range

_X = np.arange(1.0, 7.0)


def test_the_recurrence_starts_at_its_seed_and_is_nan_before() -> None:
    out = rma_seeded_at(_X, 3, 2, 2.0)
    assert np.isnan(out[:2]).all()
    assert out[2:].tolist() == pytest.approx([2.0, 8 / 3, 31 / 9, 116 / 27])


def test_a_start_past_the_series_gives_all_nan() -> None:
    assert np.isnan(rma_seeded_at(_X, 3, 6, 1.0)).all()


def test_the_mean_seed_is_the_mean_of_the_bars_it_names_at_the_last_of_them() -> None:
    out = rma_mean_seeded(_X, 3, 1, 3)  # bars 1..3 (2, 3, 4): the product ATR's seed, which skips bar 0
    assert np.isnan(out[:3]).all()
    assert out[3:].tolist() == pytest.approx([3.0, 11 / 3, 40 / 9])


def test_the_mean_seed_sums_left_to_right() -> None:
    """The product's ATR and ADX summed their seed in numba, left to right; numpy's pairwise sum differs in the last bit."""
    x = np.random.default_rng(7).random(40)
    left_to_right = 0.0
    for value in x[1:15]:
        left_to_right += value
    assert rma_mean_seeded(x, 14, 1, 14)[14] == left_to_right / 14


def test_a_mean_seed_the_series_cannot_hold_gives_all_nan() -> None:
    assert np.isnan(rma_mean_seeded(_X, 3, 4, 3)).all()


def test_the_sma_seed_is_numpys_mean_of_the_first_period_bars() -> None:
    out = rma_sma_seeded(_X, 3)
    assert np.isnan(out[:2]).all()
    assert out[2:].tolist() == pytest.approx([2.0, 8 / 3, 31 / 9, 116 / 27])
    x = np.random.default_rng(11).random(40)
    assert rma_sma_seeded(x, 14)[13] == float(np.mean(x[:14]))


def test_a_series_shorter_than_the_period_gives_all_nan() -> None:
    assert np.isnan(rma_sma_seeded(_X[:2], 3)).all()


def test_the_sma_seeded_atr_is_the_rma_of_the_true_range() -> None:
    rng = np.random.default_rng(3)
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, 60))
    high, low = close + rng.random(60), close - rng.random(60)
    expected = rma_sma_seeded(true_range(high, low, close), 7)
    np.testing.assert_array_equal(atr_sma_seeded(high, low, close, 7), expected)


def test_the_simple_atr_is_the_trailing_mean_of_the_true_range_and_reads_series() -> None:
    import pandas as pd

    rng = np.random.default_rng(4)
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, 60))
    high, low = close + rng.random(60), close - rng.random(60)
    expected = trailing_mean(true_range(high, low, close), 7)
    np.testing.assert_array_equal(atr_simple(high, low, close, 7), expected)
    np.testing.assert_array_equal(atr_simple(pd.Series(high), pd.Series(low), pd.Series(close), 7), expected)


def test_the_simple_atr_with_min_periods_warms_up_early_as_pandas_rolling_does() -> None:
    rng = np.random.default_rng(5)
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, 30))
    high, low = close + rng.random(30), close - rng.random(30)
    out = atr_simple(high, low, close, 7, min_periods=1)
    assert np.isfinite(out).all()
    np.testing.assert_array_equal(out, trailing_mean(true_range(high, low, close), 7, min_periods=1))


def test_the_first_seeded_rma_skips_a_missing_value_instead_of_going_nan_for_ever() -> None:
    x = np.array([10.0, 11.0, np.nan, 13.0, 12.0])
    out = rma_first_seeded(x, 2)
    assert np.isnan(out[2])
    np.testing.assert_array_equal(out[[0, 1, 3, 4]], [10.0, 10.5, 11.75, 11.875])


def test_the_first_seeded_atr_recovers_after_a_gap_bar() -> None:
    close = np.array([100.0, 101.0, np.nan, 102.0, 103.0, 102.5])
    high, low = close + 1.0, close - 1.0
    assert np.isfinite(atr_first_seeded(high, low, close, 3)[3:]).all()
