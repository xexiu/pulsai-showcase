"""ema_first_seeded -- the ONE EMA started at the first value (pandas / polars ``adjust=False``).

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.

The oracle is the recursion itself, written out in plain Python below -- the DEFINITION, not another
implementation's output -- so a test can only pass when the home computes what an EMA is.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import pytest

from src.domain.services.indicators.ema import ema_first_seeded


def _definition(values: list[float], span: int) -> list[float]:
    """``ema[t] = a * x[t] + (1 - a) * ema[t - 1]``, started at the first finite value; a missing bar stays NaN."""
    alpha = 2.0 / (span + 1.0)
    out: list[float] = []
    previous: float | None = None
    for value in values:
        if not math.isfinite(value):
            out.append(math.nan)
            continue
        if previous is None:
            previous = value
            out.append(previous)
            continue
        previous = alpha * value + (1.0 - alpha) * previous
        out.append(previous)
    return out


def _price_path(bars: int, seed: int) -> npt.NDArray[np.float64]:
    """A BTC-scale log random walk: the shape of the closes the regime gate reads."""
    steps = np.random.default_rng(seed).normal(0.0, 0.01, bars)
    return 30_000.0 * np.exp(np.cumsum(steps))


@pytest.mark.parametrize("span", [1, 2, 9, 21, 200])
def test_it_computes_the_definition_on_a_price_path(span: int) -> None:
    close = _price_path(3_000, seed=span)

    np.testing.assert_allclose(ema_first_seeded(close, span), _definition(close.tolist(), span), rtol=1e-12)


def test_it_starts_at_the_first_value_with_no_warm_up() -> None:
    # alpha = 2 / (3 + 1) = 0.5: 10 -> 0.5 * 20 + 0.5 * 10 = 15.
    np.testing.assert_allclose(ema_first_seeded([10.0, 20.0], 3), [10.0, 15.0])


def test_a_span_of_one_returns_the_input() -> None:
    close = _price_path(50, seed=3)

    np.testing.assert_allclose(ema_first_seeded(close, 1), close, rtol=1e-15)


def test_an_empty_series_gives_an_empty_series() -> None:
    assert ema_first_seeded(np.array([], dtype=np.float64), 9).size == 0


@pytest.mark.parametrize("span", [0, -5])
def test_a_span_below_one_is_refused(span: int) -> None:
    with pytest.raises(ValueError, match="span"):
        ema_first_seeded([1.0, 2.0], span)


def test_leading_missing_bars_wait_for_the_first_price() -> None:
    # An EMA of a warm-up indicator (an RSI's first bars are NaN) must start at its first value, not stay NaN.
    out = ema_first_seeded([math.nan, math.nan, 10.0, 11.0, 12.0], 3)

    np.testing.assert_allclose(out, [math.nan, math.nan, 10.0, 10.5, 11.25])


def test_a_missing_bar_inside_the_series_is_skipped_not_propagated() -> None:
    """The gap bar is NaN and the recursion continues as if it were absent (polars ``ignore_nulls=True``).

    Measured 2026-10-18 on [10, 11, NaN, 13], span 3: the old lab loop gave NaN on every later bar; pandas 3.0.2
    gives 12.375 and polars ``ignore_nulls=False`` 12.1667 -- three answers, so the home pins ONE.
    """
    out = ema_first_seeded([10.0, 11.0, math.nan, 13.0, math.inf, 15.0], 3)

    np.testing.assert_allclose(out, [10.0, 10.5, math.nan, 11.75, math.nan, 13.375])


def test_it_returns_a_writable_float64_copy_and_leaves_the_input_alone() -> None:
    close = np.array([1.0, 2.0, 3.0])
    out = ema_first_seeded(close, 2)
    out[0] = 99.0

    assert out.dtype == np.float64
    np.testing.assert_array_equal(close, [1.0, 2.0, 3.0])
    assert ema_first_seeded([1, 2, 3], 2).dtype == np.float64


@pytest.mark.parametrize("span", [3, 9, 12, 26, 50, 200])
def test_it_is_bit_equal_to_polars_ewm_mean_the_product_features_use(span: int) -> None:
    import polars as pl

    rng = np.random.default_rng(span)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, 5_000)))
    expected = pl.Series(close).ewm_mean(span=span, adjust=False).to_numpy()
    assert np.array_equal(ema_first_seeded(close, span).view(np.uint64), expected.view(np.uint64))


def _sma_seeded_by_loop(x: npt.NDArray[np.float64], span: int) -> npt.NDArray[np.float64]:
    alpha = 2.0 / (span + 1.0)
    out = np.full(len(x), np.nan)
    if len(x) < span:
        return out
    out[span - 1] = np.mean(x[:span])
    for i in range(span, len(x)):
        out[i] = out[i - 1] + alpha * (x[i] - out[i - 1])
    return out


@pytest.mark.parametrize("span", [2, 9, 26])
def test_the_sma_seeded_ema_starts_at_the_mean_of_the_first_span_values(span: int) -> None:
    from src.domain.services.indicators.ema import ema_sma_seeded

    rng = np.random.default_rng(span)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, 400)))
    out = ema_sma_seeded(close, span)
    assert np.isnan(out[: span - 1]).all()
    np.testing.assert_array_equal(out.view(np.uint64), _sma_seeded_by_loop(close, span).view(np.uint64))


def test_the_sma_seeded_ema_of_a_series_shorter_than_its_span_is_all_nan() -> None:
    from src.domain.services.indicators.ema import ema_sma_seeded

    assert np.isnan(ema_sma_seeded(np.array([1.0, 2.0]), 3)).all()


def test_the_sma_seeded_ema_skips_a_missing_bar_after_its_seed() -> None:
    from src.domain.services.indicators.ema import ema_sma_seeded

    out = ema_sma_seeded(np.array([1.0, 3.0, np.nan, 5.0]), 2)
    assert np.isnan(out[2])
    assert out[1] == 2.0
    assert out[3] == 2.0 + (2.0 / 3.0) * (5.0 - 2.0)
