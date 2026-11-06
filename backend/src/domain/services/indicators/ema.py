"""Exponential moving average started at the first value -- ONE home (owner, 2026-10-18).

IMPORTERS/CALLERS: ``src.domain.services.regimes.research_trend_ema`` (the research-trend regime gate),
``src.research.literature_edge_indicator_kernels`` (moved here from it, same name; its lab importers keep
importing it from there), ``fast_feature_calculator_prewarm`` (compiles it at worker boot).
AFFECTED API: ``ema_first_seeded(values, span)``. DATA SCHEMAS: none.

``ema[t] = alpha * x[t] + (1 - alpha) * ema[t - 1]``, ``alpha = 2 / (span + 1)``, ``ema[first] = x[first]``:
pandas ``ewm(span, adjust=False)`` and polars ``ewm_mean(span, adjust=False)`` on finite prices (5e-15 relative,
measured). NOT the SMA-seeded EMA with a NaN warm-up (``ema_sma_seeded`` below) -- that one
differs on every warm-up bar, so it is a different concept with a different name.

A missing value (NaN or +-inf) is SKIPPED: its bar is NaN and the recursion continues as if it were absent.
Pinned because the libraries disagree (measured on [10, 11, NaN, 13], span 3): pandas 3.0.2 gives 12.375, polars
``ignore_nulls=False`` 12.1667, and the lab loop this replaces gave NaN on every later bar -- so an EMA of an RSI,
whose first bars are NaN, came out NaN end to end.

Numba, measured 2026-10-18 on 100k bars: 0.23 ms (polars 1.29, scipy lfilter 0.40, a Python loop 90.8) and 1.8 us
on a 500-bar live slice; numpy alone cannot vectorise the recursion (the closed form overflows past ~70k bars).
The first call in a process costs ~200 ms even with the disk cache, so long-lived workers compile it at boot.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from src.shared.utils.numba_jit import njit_cached


@njit_cached
def recursion_from(values: npt.NDArray[np.float64], alpha: float, start: int, level: float) -> npt.NDArray[np.float64]:
    """``level += alpha * (x - level)`` from bar ``start`` (``level`` there), NaN before it; a missing value is skipped:
    its bar is NaN and the recursion goes on as if it were absent. polars' ewm_mean order, so bit-equal to calculate_all's
    EMA columns (indicators_home_ema_2026-10-19.txt section 2: pandas and the old ``a*x + (1-a)*w`` differ by <= 7e-15)."""
    out = np.full(values.size, np.nan)
    if start >= values.size:
        return out
    out[start] = level
    for i in range(start + 1, values.size):
        value = values[i]
        if math.isfinite(value):
            level += alpha * (value - level)
            out[i] = level
    return out


@njit_cached
def first_seeded_recursion(values: npt.NDArray[np.float64], alpha: float) -> npt.NDArray[np.float64]:
    """The recursion seeded on the first finite value: the EMA here and Wilder's RMA (rma.rma_first_seeded, alpha
    1 / period) both run it."""
    for i in range(values.size):
        if math.isfinite(values[i]):
            return recursion_from(values, alpha, i, values[i])
    return np.full(values.size, np.nan)


def ema_first_seeded(values: npt.ArrayLike, span: int) -> npt.NDArray[np.float64]:
    """EMA started at the first finite value, no warm-up NaNs; a missing value is skipped (module docstring)."""
    if span < 1:
        msg = f"EMA span must be >= 1, got {span}"
        raise ValueError(msg)
    series = np.ascontiguousarray(values, dtype=np.float64)
    return first_seeded_recursion(series, 2.0 / (span + 1.0))


def ema_sma_seeded(values: npt.ArrayLike, span: int) -> npt.NDArray[np.float64]:
    """The EMA seeded at bar ``span - 1`` with the mean of the first ``span`` values (NaN-aware), NaN before it: TA-Lib's
    and the chart's EMA; a missing value after the seed is skipped. All NaN when the series is shorter or the seed window
    holds no value."""
    if span < 1:
        msg = f"EMA span must be >= 1, got {span}"
        raise ValueError(msg)
    series = np.ascontiguousarray(values, dtype=np.float64)
    window = series[:span]
    if series.size < span or not np.isfinite(window).any():
        return np.full(series.size, np.nan)
    return recursion_from(series, 2.0 / (span + 1.0), span - 1, float(np.nanmean(window)))


__all__ = ["ema_first_seeded", "ema_sma_seeded", "first_seeded_recursion", "recursion_from"]
