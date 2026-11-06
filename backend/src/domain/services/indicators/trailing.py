"""Trailing-window statistics: the value at bar t reads bars t - window + 1 .. t, NaN before the first full window.

IMPORTERS/CALLERS: src/domain/services/trail_policies (the trailing-stop policies); catalog.INDICATOR_CALLS (the
contract test and the boot prewarm). AFFECTED API: trailing_max / trailing_min / trailing_mean / trailing_std (new), trailing_sum (2026-10-19: the
rolling sums of trading_bots_parity_volume_indicators and ampe_inspired_kernels), trailing_mean_abs_deviation (8b-ATR:
the CCI's dispersion of edge_lab and tv_rule_primitives); trailing_mean's min_periods (8b-ATR).
DATA SCHEMAS: none.

trailing_std is the population deviation (ddof 0), Pine's ta.stdev. No warm-up state: a value never depends on bars
before its own window (causal by construction). A NaN inside a window gives NaN, as numpy's max / mean do.

Max / min are a numba monotonic deque (O(n) whatever the window); mean / std a numpy window view. Measured 2026-10-18,
rolling max, best of 30, the shipped deque (NaN-aware, one kernel per side, direct comparisons): 0.46 ms vs the numpy
window view's 0.52 at 22 bars on 44,180 real BTC/USDT 5m bars; 11.7 vs 13.5 ms at 22 and 12.1 vs 25.1 ms at 200 on
1,000,000 bars; polars 20.6 and pandas 25.1 ms at 22 -- all bit-equal, clean and with NaNs. A first deque that turned
one kernel with a sign multiply ran 12-19 % SLOWER than the view at 14-22 bars: measure the shipped code, not a sketch.

REUSE-AUDIT: MOVED src/research/pine/thin_stop_path._rolling_extreme here (the same max / min; the chandelier now reads
these). src/shared/math/trailing_median is a median-only numba kernel with NaN skipping, a different statistic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from src.shared.utils.numba_jit import njit_cached

if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray

    WindowReduce = Callable[[NDArray[np.float64]], NDArray[np.float64]]


def _over_windows(x: NDArray[np.float64], window: int, reduce: WindowReduce) -> NDArray[np.float64]:
    """``reduce`` of each full trailing window, placed at the window's last bar; NaN before the first one. ``x`` is one
    series or a block of series (bars on the last axis), every row in one numpy call."""
    values = np.asarray(x, dtype=np.float64)
    out = np.full(values.shape, np.nan)
    if values.shape[-1] >= window:
        out[..., window - 1 :] = reduce(sliding_window_view(values, window, axis=-1))
    return out


def _deque_extreme_kernel(keep_max: bool, name: str) -> Callable[[NDArray[np.float64], int], NDArray[np.float64]]:
    """The max (``keep_max``) or min of each full trailing window via a deque of candidate indices; NaN before the first
    full window and wherever a NaN sits inside the window.

    ONE body, compiled once per side: ``keep_max`` is a closure constant numba folds at compile time, so each side runs as
    a hand-written kernel would. Measured 2026-10-19, best of 40, bit-equal: 0.47-0.52 ms on 44,180 real BTC/USDT 5m bars
    and 11.9-13.0 ms on 1,000,000 bars with NaNs at windows 14 / 22 / 200, within 2 % of the two hand-written copies it
    replaced; the side as a runtime flag or a jitted comparison argument cost 2-6 %, the min as the negated max 15 % and
    flipped NaN sign bits. ``name`` keeps the two disk caches apart (closures sharing a qualname share one cache index:
    measured a 440 ms recompile per process without it, ~200 ms -- the cache load -- with it)."""

    def bars(values: NDArray[np.float64], window: int) -> NDArray[np.float64]:
        n = len(values)
        out = np.full(n, np.nan)
        candidates = np.empty(n, np.int64)
        head, tail, last_nan = 0, 0, -window
        for i in range(n):
            x = values[i]
            if np.isnan(x):
                last_nan = i
            else:
                while tail > head and (values[candidates[tail - 1]] <= x if keep_max else values[candidates[tail - 1]] >= x):
                    tail -= 1
                candidates[tail] = i
                tail += 1
            if tail > head and candidates[head] <= i - window:
                head += 1
            if i >= window - 1 and last_nan <= i - window:
                out[i] = values[candidates[head]]
        return out

    bars.__name__ = bars.__qualname__ = name
    return njit_cached(bars)


_trailing_max_bars = _deque_extreme_kernel(keep_max=True, name="_trailing_max_bars")
_trailing_min_bars = _deque_extreme_kernel(keep_max=False, name="_trailing_min_bars")


def trailing_max(x: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """The highest value of the last ``window`` bars (Pine ta.highest)."""
    return _trailing_max_bars(np.asarray(x, dtype=np.float64), window)


def trailing_min(x: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """The lowest value of the last ``window`` bars (Pine ta.lowest)."""
    return _trailing_min_bars(np.asarray(x, dtype=np.float64), window)


def trailing_mean(x: NDArray[np.float64], window: int, min_periods: int | None = None) -> NDArray[np.float64]:
    """The mean of the last ``window`` bars (Pine ta.sma). With ``min_periods``: the mean of the non-NaN values among them
    wherever at least ``min_periods`` exist, partial windows at the start included (pandas ``rolling(window,
    min_periods).mean()``) -- the ATR copies that warmed up early or skipped gaps (8b-ATR, 2026-10-19)."""
    if min_periods is None:
        return _over_windows(x, window, lambda rows: rows.mean(axis=-1))
    values = np.asarray(x, dtype=np.float64)
    lead = np.full((*values.shape[:-1], window - 1), np.nan)
    rows = sliding_window_view(np.concatenate((lead, values), axis=-1), window, axis=-1)
    counts = np.count_nonzero(~np.isnan(rows), axis=-1)
    sums = np.nansum(rows, axis=-1)
    return np.where(counts >= min_periods, sums / np.maximum(counts, 1), np.nan)


def trailing_sum(x: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """The sum of the last ``window`` bars (Pine math.sum); bit-equal to summing each window's slice (numpy's pairwise
    sum), measured 2026-10-19 at windows 5..20 on 300,000 bars, 470 -> 2.3-3.2 ms against that loop."""
    return _over_windows(x, window, lambda rows: rows.sum(axis=-1))


def trailing_mean_abs_deviation(x: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """The mean absolute deviation of the last ``window`` bars from their own mean (Pine ta.dev, the CCI's dispersion);
    bit-equal to np.mean(np.abs(w - w.mean())) per window."""
    return _over_windows(x, window, lambda rows: np.abs(rows - rows.mean(axis=-1, keepdims=True)).mean(axis=-1))


def trailing_std(x: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """The population standard deviation of the last ``window`` bars (Pine ta.stdev)."""
    return _over_windows(x, window, lambda rows: rows.std(axis=-1))


__all__ = ["trailing_max", "trailing_mean", "trailing_mean_abs_deviation", "trailing_min", "trailing_std", "trailing_sum"]
