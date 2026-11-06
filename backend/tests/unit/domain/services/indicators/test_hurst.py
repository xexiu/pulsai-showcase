"""The R/S Hurst home: one window, and every trailing window at once, bit-equal to each other.

IMPORTERS / CALLERS: none (a test module). AFFECTED API: src/domain/services/indicators/hurst.py. DATA SCHEMAS: none.
"""

from __future__ import annotations

import numpy as np

from src.domain.services.indicators.hurst import CHUNK_WINDOWS, HURST_MIN_WINDOW, rescaled_range_hurst, trailing_hurst

WINDOW = 50


def _bits(values: np.ndarray) -> np.ndarray:
    return values.view(np.uint64)


def test_every_trailing_window_is_the_one_window_estimate_to_the_bit() -> None:
    returns = np.random.default_rng(3).normal(0.0, 0.002, CHUNK_WINDOWS + 500)  # crosses a chunk boundary
    trailing = trailing_hurst(returns, WINDOW)
    one_by_one = np.array([rescaled_range_hurst(returns[i - WINDOW + 1 : i + 1]) if i >= WINDOW - 1 else np.nan
                           for i in range(returns.size)])  # fmt: skip
    assert np.array_equal(_bits(trailing), _bits(one_by_one))


def test_nothing_is_read_before_the_first_full_window_nor_from_a_too_short_one() -> None:
    returns = np.random.default_rng(4).normal(0.0, 0.002, 200)
    assert np.isnan(trailing_hurst(returns, WINDOW)[: WINDOW - 1]).all()
    assert np.isnan(trailing_hurst(returns, HURST_MIN_WINDOW - 1)).all()
    assert np.isnan(rescaled_range_hurst(returns[: HURST_MIN_WINDOW - 1]))


def test_a_flat_or_broken_window_has_no_hurst() -> None:
    flat = np.zeros(WINDOW)
    broken = np.random.default_rng(5).normal(0.0, 0.002, WINDOW)
    broken[10] = np.nan
    assert np.isnan(rescaled_range_hurst(flat))
    assert np.isnan(rescaled_range_hurst(broken))
    assert np.isnan(trailing_hurst(broken, WINDOW)[-1])


def test_alternating_returns_read_mean_reverting_and_persistent_ones_trending() -> None:
    alternating = np.tile([0.001, -0.001], 144)  # every move undone the next bar
    rng = np.random.default_rng(6)
    persistent = np.empty(288)
    persistent[0] = 0.0
    for i in range(1, persistent.size):  # AR(1), phi 0.9: moves keep going
        persistent[i] = 0.9 * persistent[i - 1] + rng.normal(0.0, 0.001)
    assert rescaled_range_hurst(alternating) < 0.5 < rescaled_range_hurst(persistent)
