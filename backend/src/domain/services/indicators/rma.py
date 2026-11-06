"""Wilder's running moving average (RMA): seeded on the first value, or on a mean of the first bars; the ATRs on it.

IMPORTERS/CALLERS: indicators/chandelier.chandelier_exit (the runner trail the live engine and the lab read), the lab's
rma_atr_bands_kernels, ampe_inspired_kernels, ampe_inspired_meta_label_kernels, volume_profile_vah_breakout_kernels,
volume_profile_val_kernels, rl_edge/data (ATR features); catalog.INDICATOR_CALLS. The mean-seeded RMA: the
product's features/numba_volatility.calculate_atr_numba and numba_trend.calculate_adx_numba, targets/
trend_following_target (ADX), and the lab's alpha_trend_style_kernels, hma_alligator_kernels.smma and the
trading_bots_parity family's ATR (the RSIs on it moved to indicators.rsi, 2026-10-19). AFFECTED API: rma_first_seeded / atr_first_seeded (MOVED from
rma_atr_bands_kernels.wilder_rma / wilder_atr, rl_edge/data._wilder_smooth / atr); rma_seeded_at / rma_mean_seeded /
rma_sma_seeded / atr_sma_seeded (new 2026-10-19: the recurrence those seven copies wrote inline). DATA SCHEMAS: none.

Two recurrences, kept apart because they round differently:
- first-seeded: rma[0] = x[0], then rma[t] = x[t] / period + (1 - 1 / period) * rma[t - 1] -- pandas ewm(alpha=1/period,
  adjust=False) to float precision;
- mean-seeded: a seed at one bar, then rma[t] = (rma[t - 1] * (period - 1) + x[t]) / period -- Wilder's own form, the
  one TA-Lib and the product's ATR / ADX use. Its seed is a mean of the first bars, summed the way each caller summed
  it: ``rma_mean_seeded`` left to right (numba, the product's ATR and ADX), ``rma_sma_seeded`` numpy's pairwise mean
  of the first ``period`` bars (the SMMA / Pine convention); ``rma_seeded_at`` takes a seed the caller computed.
  The two sums differ in the last bit for 8+ bars, so one rule for both would have moved every caller's output.

Why a numba loop, measured 2026-10-18 on real BTC/USDT 5m bars (44,180) and 1,000,000 synthetic ones, best of 30, the
RMA of the true range at period 22: numba loop 2.5 ms, scipy lfilter 4.9, pandas ewm 8.8, polars ewm_mean 12.1, a python
loop 245 (1M bars). Only the numba and python loops are bit-equal to each other (the moved rl_edge loop included);
pandas / polars / scipy differ by up to 2.3e-15 relative.

REUSE-AUDIT: MOVED here from the lab (rma_atr_bands_kernels, rl_edge/data held the same recursion; the domain may not
import the lab). shared/research/uncertainty_zones.ema is a different statistic (SMA seed, alpha 2/(n+1)).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from src.domain.services.indicators.ema import first_seeded_recursion
from src.domain.services.indicators.trailing import trailing_mean
from src.domain.services.indicators.true_range import true_range
from src.shared.utils.numba_jit import njit_cached

if TYPE_CHECKING:
    from numpy.typing import ArrayLike, NDArray


def rma_first_seeded(x: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Wilder's RMA (alpha = 1 / period) seeded on the first finite value: the ema home's recursion at alpha 1 / period
    (one kernel, bit-equal to the loop it replaced on finite bars). A missing value is skipped -- its bar is NaN and the
    recursion continues -- where the old loop went NaN on every later bar (8b-ATR, 2026-10-19)."""
    return first_seeded_recursion(np.ascontiguousarray(x, dtype=np.float64), 1.0 / period)


def atr_first_seeded(high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Wilder ATR: the RMA of the true range, seeded on the first bar's high - low."""
    return rma_first_seeded(true_range(high, low, close), period)


@njit_cached
def _rma_rows_seeded_at(rows: NDArray[np.float64], period: int, start: int, seeds: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each row's Wilder RMA from bar ``start`` (its seed there), all rows in one pass over the bars; NaN before."""
    count, n = rows.shape
    out = np.full((count, n), np.nan)
    if start >= n:
        return out
    for r in range(count):
        out[r, start] = seeds[r]
    for i in range(start + 1, n):
        for r in range(count):
            out[r, i] = (out[r, i - 1] * (period - 1) + rows[r, i]) / period
    return out


@njit_cached
def _left_to_right_means(rows: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each row's mean, summed left to right (numba's np.mean -- numpy's own is pairwise and differs in the last bit)."""
    means = np.empty(rows.shape[0])
    for r in range(rows.shape[0]):
        means[r] = np.mean(rows[r])
    return means


def rma_seeded_at(x: NDArray[np.float64], period: int, start: int, seed: float) -> NDArray[np.float64]:
    """Wilder's RMA from bar ``start``: ``seed`` there, then (rma[t - 1] * (period - 1) + x[t]) / period; NaN before.

    A ``start`` past the series gives all NaN."""
    row = np.ascontiguousarray(x, dtype=np.float64)[None, :]
    return _rma_rows_seeded_at(row, period, start, np.array([seed], dtype=np.float64)).ravel()


def rma_mean_seeded(x: NDArray[np.float64], period: int, seed_from: int, seed_count: int) -> NDArray[np.float64]:
    """Wilder's RMA seeded at the last of the ``seed_count`` bars from ``seed_from`` with their mean, summed left to right;
    all NaN when the series does not hold those bars.

    ``x`` is one series, or a (series, bars) block whose rows are smoothed in ONE pass: measured 2026-10-19 on 1,000,000
    synthetic bars, best of 30, three rows 12.5 ms against 24.6 for three passes (the rows' divisions overlap) -- what
    lets the ADX smooth its ATR and both DMs as fast as the single kernel it replaced; one row 8.0 ms either way."""
    block = np.ascontiguousarray(x, dtype=np.float64)
    is_block = block.ndim > 1  # (series, bars); a 1D series is a one-row block
    rows = block if is_block else block[None, :]
    start = seed_from + seed_count - 1
    if start >= rows.shape[1]:
        out = np.full(rows.shape, np.nan)
    else:
        out = _rma_rows_seeded_at(rows, period, start, _left_to_right_means(rows[:, seed_from : start + 1]))
    return out if is_block else out[0]


def rma_sma_seeded(x: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Wilder's RMA seeded at bar ``period - 1`` with numpy's mean of the first ``period`` bars (the SMMA); all NaN when
    the series is shorter."""
    values = np.asarray(x, dtype=np.float64)
    if len(values) < period:
        return np.full(len(values), np.nan)
    return rma_seeded_at(values, period, period - 1, float(np.mean(values[:period])))


def atr_sma_seeded(high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Wilder ATR seeded at bar ``period - 1`` with the mean of the first ``period`` true ranges (Pine's ta.atr seed)."""
    return rma_sma_seeded(true_range(high, low, close), period)


def atr_simple(high: ArrayLike, low: ArrayLike, close: ArrayLike, period: int, min_periods: int | None = None) -> NDArray[np.float64]:
    """The simple-average ATR: the trailing mean of the last ``period`` true ranges (pandas ``tr.rolling(period).mean()``,
    bit-equal); ``min_periods`` warms up early and skips NaN as pandas does. Series or arrays in."""
    tr = true_range(np.asarray(high, dtype=np.float64), np.asarray(low, dtype=np.float64), np.asarray(close, dtype=np.float64))
    return trailing_mean(tr, period, min_periods)


__all__ = ["atr_first_seeded", "atr_simple", "atr_sma_seeded", "rma_first_seeded", "rma_mean_seeded", "rma_seeded_at", "rma_sma_seeded"]
