"""The Chandelier Exit: a runner's stop hung an ATR multiple off the window's extreme.

IMPORTERS/CALLERS: src/domain/services/trail_policies (ChandelierAtrTrail), the lab's thin_stop_path.chandelier_trails
(the frame adapter ~20 lab screens read), engine/strategies/arm74_core and engine/replay/model_book_replay (the live
engine's runner trail); catalog.INDICATOR_CALLS. AFFECTED API: chandelier_exit, CHANDELIER_LENGTH, CHANDELIER_MULT
(MOVED from thin_stop_path.chandelier_arrays / CHAND_LEN / CHAND_MULT). DATA SCHEMAS: none.

long stop  = highest high of the last ``length`` bars - mult x ATR(length)
short stop = lowest low of the last ``length`` bars + mult x ATR(length)
with the first-seeded Wilder ATR (rma.atr_first_seeded) -- the trail the live engine has run since 2026-10-14, moved here
unchanged: bit-equal to the lab's chandelier_arrays on real bars, clean and with NaNs. Its two parts are timed in their
own homes (trailing.trailing_max / trailing_min, rma.rma_first_seeded); this module only composes them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np

from src.domain.services.indicators.rma import atr_first_seeded
from src.domain.services.indicators.trailing import trailing_max, trailing_min

if TYPE_CHECKING:
    from numpy.typing import NDArray

#: Bars in the window and in the ATR -- 22, the classic chandelier (about one trading month on dailies).
CHANDELIER_LENGTH: Final[int] = 22
#: ATR multiples between the window's extreme and the stop.
CHANDELIER_MULT: Final[float] = 3.0


def chandelier_exit(
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    close: NDArray[np.float64],
    length: int = CHANDELIER_LENGTH,
    mult: float = CHANDELIER_MULT,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """(long stop, short stop) per bar; NaN until the window is full."""
    h, lo, c = (np.asarray(v, dtype=np.float64) for v in (high, low, close))
    atr = atr_first_seeded(h, lo, c, length)
    return trailing_max(h, length) - mult * atr, trailing_min(lo, length) + mult * atr


__all__ = ["CHANDELIER_LENGTH", "CHANDELIER_MULT", "chandelier_exit"]
