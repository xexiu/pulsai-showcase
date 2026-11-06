"""The ONE zero-dispersion guard, pinned by the measurement that chose it (rerun to re-derive it).

The measurement is the test: it recomputes the float noise of CONSTANT series with every estimator
the product uses, and the smallest REAL dispersion the product sees, then asserts the threshold
separates them with margin -- and that no ABSOLUTE threshold could (why the guard is relative).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.shared.constants import NEAR_ZERO_STD_THRESHOLD
from src.shared.math.zero_dispersion import is_near_zero_std, is_near_zero_variance

#: Values a constant series takes in the product: a 1e-8-priced coin, a 1e-5 coin, returns,
#: probabilities, BTC, a 1e6 index, quote volume / open interest in USD.
_CONSTANT_VALUES = (1e-8, 1.234567e-5, 1e-3 + 1e-9, 0.1, 0.7, 1.0, 30000.37, 97123.45, 1e6 + 0.1, 1234567890.37)
_LENGTHS = (2, 3, 100, 10_000, 100_000)
_MARGIN = 100.0


def _relative(std: float, mean: float) -> float:
    return std / max(abs(mean), 1.0)


def _estimates(series: np.ndarray) -> list[float]:
    """Every std estimator a product guard sits behind: numpy, pandas, and the fsum two-pass."""
    values = series.tolist()
    mean = math.fsum(values) / len(values)
    fsum_std = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / len(values))
    return [float(np.std(series)), float(np.std(series, ddof=1)), math.sqrt(float(np.var(series))), float(pd.Series(series).std()), fsum_std]


def _constant_series_noise() -> tuple[float, float]:
    """(max absolute std, max std / max(|mean|, 1)) over constant series -- pure float noise."""
    worst_abs = worst_rel = 0.0
    for value in _CONSTANT_VALUES:
        for n in _LENGTHS:
            for std in _estimates(np.full(n, value)):
                worst_abs = max(worst_abs, std)
                worst_rel = max(worst_rel, _relative(std, value))
    return worst_abs, worst_rel


def _same_stop_trade_returns() -> np.ndarray:
    """Per-trade returns when every trade exits at the SAME -2% stop: ratio-minus-one arithmetic."""
    entries = np.random.default_rng(1).uniform(20_000.0, 110_000.0, 500)
    return (entries * (1 - 0.02) - entries) / entries - 0.0016


def _one_tick_window(price: float, tick: float) -> np.ndarray:
    window = np.full(20, price)
    window[-1] += tick
    return window


#: (label, series) -- the smallest genuine dispersion product guards see.
_REAL = (
    ("BTC 1-tick close window", _one_tick_window(97123.4, 0.01)),
    ("stablecoin 1-tick close window", _one_tick_window(1.0001, 0.0001)),
    ("BTC 1-tick return window", np.diff(_one_tick_window(97123.4, 0.01)) / 97123.4),
    ("model outputs 1e-11 apart", 1e-3 + 1e-11 * np.arange(50)),
)


def _smallest_real() -> tuple[float, float]:
    """(min absolute std, min relative std) over genuinely varying product series."""
    stds = [(float(np.std(s, ddof=1)), float(np.mean(s))) for _, s in _REAL]
    return min(s for s, _ in stds), min(_relative(s, m) for s, m in stds)


def test_no_absolute_threshold_can_separate_noise_from_real_dispersion() -> None:
    noise_abs, _ = _constant_series_noise()
    real_abs = float(np.std(_one_tick_window(1.5e-8, 1e-12), ddof=1))
    assert noise_abs > 1e5 * real_abs, "if this fails, an absolute threshold became possible -- re-decide"


def test_relative_threshold_sits_above_measured_float_noise_with_margin() -> None:
    _, noise_rel = _constant_series_noise()
    trade_noise = _relative(float(np.std(_same_stop_trade_returns())), float(np.mean(_same_stop_trade_returns())))
    assert max(noise_rel, trade_noise) * _MARGIN < NEAR_ZERO_STD_THRESHOLD


def test_relative_threshold_sits_below_smallest_real_dispersion_with_margin() -> None:
    _, real_rel = _smallest_real()
    assert real_rel > NEAR_ZERO_STD_THRESHOLD * _MARGIN


@pytest.mark.parametrize("value", _CONSTANT_VALUES)
@pytest.mark.parametrize("n", _LENGTHS)
def test_constant_series_is_degenerate_at_every_scale(value: float, n: int) -> None:
    series = np.full(n, value)
    assert all(is_near_zero_std(std, value) for std in _estimates(series))
    assert is_near_zero_variance(float(np.var(series)), value)


def test_same_stop_trade_returns_are_degenerate() -> None:
    returns = _same_stop_trade_returns()
    assert is_near_zero_std(float(np.std(returns)), float(np.mean(returns)))


@pytest.mark.parametrize(("label", "series"), _REAL)
def test_tiny_real_dispersion_is_not_degenerate(label: str, series: np.ndarray) -> None:
    mean = float(np.mean(series))
    assert not is_near_zero_std(float(np.std(series, ddof=1)), mean), label
    assert not is_near_zero_variance(float(np.var(series, ddof=1)), mean), label


def test_the_unit_floor_is_the_known_edge_for_sub_unit_price_windows() -> None:
    """``max(|mean|, 1)`` floors sub-unit data at an ABSOLUTE 1e-12 (needed: returns carry ~eps of
    noise whatever their size). Its cost, stated: a one-tick price window of a 1e-5 coin still reads
    real (2.2e-11), a 1e-8 coin's (2.2e-13) reads degenerate. The only product guard over raw price
    windows (feature_volatility's MAD ratio) has MAD == 0 as its numerator on a one-tick window, so
    the answer it publishes is 0.0 either way."""
    pepe = _one_tick_window(1.234e-5, 1e-10)
    micro = _one_tick_window(1.5e-8, 1e-12)
    assert not is_near_zero_std(float(np.std(pepe, ddof=1)), float(np.mean(pepe)))
    assert is_near_zero_std(float(np.std(micro, ddof=1)), float(np.mean(micro)))


def test_nan_is_degenerate_because_nothing_can_be_divided_by_it() -> None:
    assert is_near_zero_std(math.nan, 0.0)
    assert is_near_zero_variance(math.nan, 0.0)


def test_arrays_are_judged_elementwise_against_their_own_scale() -> None:
    std = np.array([1e-4, 1e-4, 0.0, np.nan, 2e-12])
    mean = np.array([1.234e9, 1.0, 5.0, 1.0, 0.5])
    assert is_near_zero_std(std, mean).tolist() == [True, False, True, True, False]
    assert is_near_zero_variance(std**2, mean).tolist() == [True, False, True, True, False]


def test_scalar_inputs_answer_a_plain_bool() -> None:
    assert type(is_near_zero_std(0.0, 1.0)) is bool
    assert type(is_near_zero_variance(np.float64(1.0), np.float64(0.5))) is bool
