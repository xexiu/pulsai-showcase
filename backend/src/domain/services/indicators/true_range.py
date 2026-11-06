"""The true range of each bar: the widest of its own range and its gaps from the previous close.

IMPORTERS/CALLERS: features/numba_volatility.calculate_atr_numba (the product ATR), infrastructure/ml/backtester_atr.
build_atr_series, infrastructure/ml/position_sizers.atr_price_ratio_at, and the lab ATRs that computed it inline until
2026-10-18 (adaptive_trend_momentum.average_true_range, edge_hunt/ema200_bos_fvg_rule._causal_atr, novel_indicator_oos.
_atr / k_vortex_cross, rl_edge/data.atr, rma_atr_bands_kernels.wilder_atr, trading_bots_parity_long_signal_b.
_atr_wilder); catalog.INDICATOR_CALLS. AFFECTED API: true_range (new). DATA SCHEMAS: none.

A missing previous close -- the first bar, or a NaN close -- gives high - low: Pine's ta.tr(handle_na=true), the rule
ta.atr uses, and what the product ATR and the position sizer already did. A NaN high or low gives NaN. One series of
bars; a bars x assets panel goes column by column.

Why a numba loop, measured 2026-10-18 on real BTC/USDT 5m bars (44,180) and 1,000,000 synthetic ones, best of 30:
numba loop 0.93 ms, polars 2.6, numba over whole arrays 3.4, numpy 7.4 (1M bars); the product ATR built on it 9.3 ms
against the old single kernel's 9.4, while numpy's true range under the same smoother takes 15.6. Every variant is
bit-equal to the copies it replaced on the real bars; they differ only where a previous close is NaN, where the numpy
copies returned NaN (which then poisoned every later ATR) and Pine's rule returns high - low.

REUSE-AUDIT: MOVED here from the ten copies above (the one-definition guard and the expression-clone index named
them); the domain may not import the lab or infrastructure, so they import this.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from src.shared.utils.numba_jit import njit_cached

if TYPE_CHECKING:
    from numpy.typing import NDArray


def true_range(high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64]) -> NDArray[np.float64]:
    """max(high - low, |high - previous close|, |low - previous close|) per bar; high - low with no previous close.

    Any array-like (a Series, a list, float32) is read as float64 first, as the numpy copies it replaced did. A block of
    series (one asset per row, bars on the last axis) gives one true range per row."""
    arrays = [np.ascontiguousarray(v, dtype=np.float64) for v in (high, low, close)]
    if arrays[0].ndim == 1:
        return _true_range_bars(*arrays)
    return np.stack([_true_range_bars(*row) for row in zip(*arrays, strict=True)])


@njit_cached
def _true_range_bars(high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64]) -> NDArray[np.float64]:
    out = np.empty(len(close))
    for i in range(len(close)):
        span = high[i] - low[i]
        previous = close[i - 1] if i > 0 else np.nan
        out[i] = span if np.isnan(previous) else max(span, abs(high[i] - previous), abs(low[i] - previous))
    return out


__all__ = ["true_range"]
