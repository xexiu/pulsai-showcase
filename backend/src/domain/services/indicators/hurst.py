"""The rescaled-range (R/S) Hurst exponent of a window of returns: near 0.5 a random walk, below it mean-reverting, above
it trending (persistent).

IMPORTERS/CALLERS: research/pine/article_ml_5m/meta_l_features (PLAN_SOL_SWITCH 13.32's momentum features). The same
estimator as research/edge_hunt/hypotheses/hurst_sa._hurst_rs (bit-equal on every trailing window, measured below); that
bootstrap script keeps its copy until 8b-REST repoints it here.
tests/unit/domain/services/indicators/test_hurst.py. AFFECTED API: rescaled_range_hurst, trailing_hurst, HURST_MIN_WINDOW,
FLAT_SPREAD, CHUNK_WINDOWS (new). DATA SCHEMAS: none.

H = log(R / S) / log(n): R the range of the window's cumulative demeaned returns, S their standard deviation (ddof 1).
Two other lab estimators differ on purpose and stay where they are: sa_hurst_multifract_features._rolling_hurst drops
non-finite values and shifts one bar; novel_indicator_oos._hurst_roll uses ddof 0 and fills 0.5 -- 8b-REST's hurst row.

MEASURED 2026-10-29, window 288 (one day of 5m bars), best of 3 (the 1M python loop: 1 run), against the lab's python loop
over hurst_sa._hurst_rs on each trailing window (polars has no rolling cumulative range to express R):
                                         69,695 real SOL 5m returns    1,000,000 synthetic    bit-equal to the lab loop
  python loop over numpy (the lab's)       4,957 ms                      78,147 ms
  numba loop                                 225.5 ms                     3,625 ms              no (3.3e-16 / 7.8e-16)
  numpy over chunked sliding windows         327.6 ms                     4,737 ms              yes
The shipped trailing_hurst is the chunked numpy one: the fastest bit-equal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

if TYPE_CHECKING:
    from numpy.typing import NDArray

#: The shortest window an estimate is read from; shorter ones are NaN.
HURST_MIN_WINDOW: Final[int] = 20
#: A spread at or below this is no spread: the window is flat and has no Hurst.
FLAT_SPREAD: Final[float] = 1e-12
#: Windows reduced at once: bounds the sliding view's working memory (window x CHUNK_WINDOWS floats).
CHUNK_WINDOWS: Final[int] = 20_000


def rescaled_range_hurst(x: NDArray[np.float64]) -> float:
    """Classic R/S Hurst of one window of returns; NaN when shorter than HURST_MIN_WINDOW or degenerate (a non-finite
    value, no spread, no range)."""
    n = len(x)
    if n < HURST_MIN_WINDOW:
        return float("nan")
    y = x - np.nanmean(x)
    if not np.isfinite(y).all() or np.nanstd(y) < FLAT_SPREAD:
        return float("nan")
    z = np.cumsum(y)
    r = float(np.nanmax(z) - np.nanmin(z))
    s = float(np.nanstd(y, ddof=1))
    if s < FLAT_SPREAD or r <= 0:
        return float("nan")
    return float(np.log(r / s) / np.log(n))


def trailing_hurst(returns: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """rescaled_range_hurst of the ``window`` returns ENDING at each index (index i reads returns[i - window + 1 .. i],
    known at bar i's close), every window reduced at once; NaN before the first full window and where it is degenerate."""
    values = np.asarray(returns, dtype=np.float64)
    out = np.full(values.size, np.nan)
    if window < HURST_MIN_WINDOW or values.size < window:
        return out
    windows = sliding_window_view(values, window)
    for start in range(0, windows.shape[0], CHUNK_WINDOWS):
        x = windows[start : start + CHUNK_WINDOWS]
        y = x - np.nanmean(x, axis=1, keepdims=True)
        z = np.cumsum(y, axis=1)
        spread_range = z.max(axis=1) - z.min(axis=1)
        spread = np.nanstd(y, axis=1, ddof=1)
        flat = (np.nanstd(y, axis=1) < FLAT_SPREAD) | ~np.isfinite(y).all(axis=1) | (spread < FLAT_SPREAD) | (spread_range <= 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            hurst = np.log(spread_range / spread) / np.log(window)
        out[window - 1 + start : window - 1 + start + x.shape[0]] = np.where(flat, np.nan, hurst)
    return out


__all__ = ["CHUNK_WINDOWS", "FLAT_SPREAD", "HURST_MIN_WINDOW", "rescaled_range_hurst", "trailing_hurst"]
