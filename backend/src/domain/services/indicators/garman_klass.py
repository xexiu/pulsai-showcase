"""Garman-Klass variance: one bar's variance read from its own open, high, low and close.

IMPORTERS/CALLERS: src/research/pine/article_ml_5m (the VOL-DIR-TREND volatility forecasters, sol_v2_volatility_switch:
the HAR / ARIMA / SARIMA / ARIMAX / Prophet series is its log); catalog.INDICATOR_CALLS. AFFECTED API:
garman_klass_variance, OPEN_CLOSE_WEIGHT (new). DATA SCHEMAS: none.

sigma^2 = 0.5 x ln(high / low)^2 - (2 ln 2 - 1) x ln(close / open)^2 (Garman & Klass, 1980): the range carries the
variance and the open-to-close move is taken back out. Never negative on a real bar (|ln(close / open)| <= ln(high /
low)); 0 on a bar that never moved; NaN where a price is NaN. Each bar reads only itself.

MEASURED 2026-10-23, best of 15, bit-equality on the uint64 view against the numpy formula:
                        140,526 real SOL/USDT 5m bars    1,000,000 synthetic    bit-equal
  numpy                  1.00 ms                          9.70 ms                (reference)
  numba loop             0.92 ms                          7.02 ms                no
  numba, whole arrays    0.94 ms                          7.14 ms                yes
  polars expressions     1.34 ms                          8.68 ms                yes
The shipped one is numba over whole arrays: the fastest bit-equal kernel (the loop is faster by 2 % and differs in the
last bit).

REUSE-AUDIT: searched src for a Garman-Klass (or range-based) bar variance -- none exists; the lab's HAR records read
close-to-close returns (edge_hunt har_log_vol_training_new._rv).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

import numpy as np

from src.shared.utils.numba_jit import njit_cached

if TYPE_CHECKING:
    from numpy.typing import NDArray

#: Garman & Klass's weight on the open-to-close move.
OPEN_CLOSE_WEIGHT: Final[float] = 2.0 * math.log(2.0) - 1.0


def garman_klass_variance(
    open_: NDArray[np.float64], high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Each bar's Garman-Klass variance from its own open, high, low and close."""
    o, h, lo, c = (np.ascontiguousarray(v, dtype=np.float64) for v in (open_, high, low, close))
    return _garman_klass_bars(o, h, lo, c, OPEN_CLOSE_WEIGHT)


@njit_cached
def _garman_klass_bars(
    open_: NDArray[np.float64], high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64], weight: float
) -> NDArray[np.float64]:
    return 0.5 * np.log(high / low) ** 2 - weight * np.log(close / open_) ** 2


__all__ = ["OPEN_CLOSE_WEIGHT", "garman_klass_variance"]
