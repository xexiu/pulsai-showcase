"""Trailing-window statistics: each value against a plain per-bar loop on the same bars.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from src.domain.services.indicators.trailing import trailing_max, trailing_mean, trailing_min, trailing_std

_RNG = np.random.default_rng(7)
_X = 100.0 + np.cumsum(_RNG.normal(0.0, 1.0, 60))
_WINDOW = 5


def _by_loop(x: np.ndarray, window: int, reduce: Callable[[np.ndarray], float]) -> np.ndarray:
    return np.array([reduce(x[t - window + 1 : t + 1]) if t >= window - 1 else np.nan for t in range(len(x))])


@pytest.mark.parametrize(
    ("indicator", "reduce"),
    [(trailing_max, np.max), (trailing_min, np.min), (trailing_mean, np.mean), (trailing_std, np.std)],
)
def test_each_bar_reads_its_own_window_and_nan_before_the_first_full_one(
    indicator: Callable[[np.ndarray, int], np.ndarray], reduce: Callable[[np.ndarray], float]
) -> None:
    np.testing.assert_allclose(indicator(_X, _WINDOW), _by_loop(_X, _WINDOW, reduce), rtol=1e-12, equal_nan=True)


def test_a_series_shorter_than_the_window_is_all_nan() -> None:
    assert np.isnan(trailing_max(_X[:3], _WINDOW)).all()


@pytest.mark.parametrize(("indicator", "reduce"), [(trailing_max, np.max), (trailing_min, np.min)])
def test_a_nan_inside_a_window_gives_nan_there_as_numpy_does(
    indicator: Callable[[np.ndarray, int], np.ndarray], reduce: Callable[[np.ndarray], float]
) -> None:
    x = _X.copy()
    x[[10, 11, 40]] = np.nan
    np.testing.assert_array_equal(indicator(x, _WINDOW), _by_loop(x, _WINDOW, reduce))


@pytest.mark.parametrize("min_periods", [1, 3, _WINDOW])
def test_a_mean_with_min_periods_skips_nan_and_reads_partial_windows_as_pandas_rolling_does(min_periods: int) -> None:
    import pandas as pd

    x = _X.copy()
    x[[2, 10, 11, 12, 13, 14, 40]] = np.nan  # a lone gap, a run as long as the window, a gap at the start
    expected = pd.Series(x).rolling(_WINDOW, min_periods=min_periods).mean().to_numpy()
    np.testing.assert_allclose(trailing_mean(x, _WINDOW, min_periods=min_periods), expected, rtol=1e-15, equal_nan=True)


def test_a_mean_with_min_periods_reads_each_row_of_a_block_on_its_own() -> None:
    block = np.vstack([_X, _X[::-1]])
    block[1, 20] = np.nan
    out = trailing_mean(block, _WINDOW, min_periods=2)
    for row, series in zip(out, block, strict=True):
        np.testing.assert_array_equal(row, trailing_mean(series, _WINDOW, min_periods=2))


def test_the_trailing_sum_adds_each_full_window_and_is_nan_before() -> None:
    from src.domain.services.indicators.trailing import trailing_sum

    out = trailing_sum(np.array([1.0, 2.0, 3.0, 4.0]), 3)
    assert np.isnan(out[:2]).all()
    assert out[2:].tolist() == [6.0, 9.0]


def test_the_mean_absolute_deviation_reads_each_window_around_its_own_mean() -> None:
    from src.domain.services.indicators.trailing import trailing_mean_abs_deviation

    expected = _by_loop(_X, _WINDOW, lambda w: float(np.mean(np.abs(w - w.mean()))))
    np.testing.assert_array_equal(trailing_mean_abs_deviation(_X, _WINDOW), expected)
