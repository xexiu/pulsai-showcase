"""Did a price reach a level? The ONE touch rule of every walk and every live chart -- stops, targets, breakeven,
liquidation -- and the one stop ratchet.

IMPORTERS/CALLERS: src/infrastructure/ml/backtester_exit_thin_stop (the graded kernel: stop fill, targets, breakeven,
the ratchet), src/research/engine/strategies/model_book_core (every live model-book chart: the same tests and the same
ratchet), src/research/pine/sr_sweep_signals_5m/{band_flip_live,burst_live,sltp_walk} (level_touched, from inside
compiled kernels); tests/unit/shared/math/test_bar_level_touch.py. AFFECTED API: TOUCH_REL_TOL moved here from
backtester_exit_thin_stop; price_reached, target_reached and tightened are new; level_touched now honours the tie
(TOUCH-TIE).
DATA SCHEMAS: none.

WHY ONE HOME (owner, 2026-10-26: "SOT, centralized for ALL engines"): the breakeven touch was written three times -- the
kernel inline (`h[t] >= be_px - be_tol`), the live engine's `_touched`, and the lab walks' `level_touched` (without the
tie) -- held equal only by replay parity and a shared constant. A rule written three times is three rules the day one
of them changes.

PERF (2026-10-26, best of 30, the touch over a level per bar and the ratchet; bit-equal = np.array_equal against the
inline code each replaces, the ratchet on the .view(np.uint64) bits):
    68,256 real SOL 5m bars  touch: numba inline 0.014 ms | numba price_reached 0.015 ms | numpy 0.059 | polars 0.091
    1,000,000 bars           touch: numba inline 0.249 ms | numba price_reached 0.252 ms | numpy 1.518 | polars 1.341
                             ratchet: numba inline 0.325 ms | numba tightened 0.303 ms
  bit-equal on both series (every planted tie row touched: 69 of 69, 1,004 of 1,004). Compiled scalar functions called
  inside the kernels' own loops: as fast as the inline spelling and ~5x numpy / polars; plain python calls them too.

REUSE-AUDIT: considered src/shared/math/linear_isolated_perp.py -- it computes the liquidation PRICE, is pure python and
is imported by the product backtester, so a numba import does not belong there; the touch is a separate question.
"""

from __future__ import annotations

from src.shared.utils.numba_jit import njit_cached

#: TOUCH-TIE (2026-10-14): a level is built as e * (1 +- r * s), and float rounding can put it one step past the price
#: it stands for -- entry 0.1960 + 0.0008 came out 0.19680000000000003, so a high of exactly 0.1968 missed the stop
#: (ADA, 2 of 91 trades; the live chart, fill + d, hit them). A price within this relative distance of a level touches
#: it, as a resting stop or limit is triggered by a touch; the fill stays the level itself.
TOUCH_REL_TOL = 1e-12


@njit_cached
def price_reached(direction: int, price: float, level: float) -> bool:
    """True when ``price`` has reached ``level`` moving in ``direction`` (+1 up to it, -1 down to it), a price within
    TOUCH_REL_TOL of the level counting as a touch: a target or breakeven reached in the trade's favour is
    ``direction = side``, a stop reached against it ``direction = -side``."""
    tol = abs(level) * TOUCH_REL_TOL
    if direction > 0:
        return price >= level - tol
    return price <= level + tol


@njit_cached
def level_touched(side: int, low: float, high: float, level: float) -> bool:
    """True when the bar's adverse extreme for `side` (+1 long, -1 short) reaches `level`; a flat book (0) never does."""
    if side > 0:
        return price_reached(-1, low, level)
    if side < 0:
        return price_reached(1, high, level)
    return False


@njit_cached
def target_reached(side: int, low: float, high: float, level: float) -> bool:
    """True when the bar's favourable extreme for `side` reaches `level` -- a target or the breakeven trigger: a long's
    high up to it, a short's low down to it; a flat book (0) never does. The twin of level_touched."""
    if side > 0:
        return price_reached(1, high, level)
    if side < 0:
        return price_reached(-1, low, level)
    return False


@njit_cached
def tightened(stop: float, level: float, side: int) -> float:
    """The stop moved to ``level`` only when that is in the trade's favour -- for a long only ever up, for a short only
    ever down."""
    return max(stop, level) if side > 0 else min(stop, level)
