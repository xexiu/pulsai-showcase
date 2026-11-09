"""A window of minutes in a day that may run across midnight -- the one home of "is this minute inside it".

IMPORTERS/CALLERS: research.pine.article_ml_5m.sol_v2_sessions (the trading sessions a SOL bar opens in),
research.pine.sr_sweep_signals_5m.liquidity_targets (the sweep engine's session highs / lows);
tests/unit/domain/services/test_daily_window.py. AFFECTED API: in_daily_window (new). DATA SCHEMAS: none.

WHY (SESSION-SWITCH, 2026-10-23): the session test needed this, and liquidity_targets already held it as an inline
two-branch expression; the one-definition guard refused a second copy, so the concept moved here and both import it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.enums import MINUTES_PER_DAY

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


def in_daily_window(minute_of_day: NDArray[np.int64], start: int, end: int) -> NDArray[np.bool_]:
    """True where ``minute_of_day`` (0 .. 1439) falls in [start, end); a window whose end is not after its start runs
    across midnight, and start == end is the whole day (the two-branch test it replaced read it so)."""
    return (minute_of_day - start) % MINUTES_PER_DAY < ((end - start) % MINUTES_PER_DAY or MINUTES_PER_DAY)
