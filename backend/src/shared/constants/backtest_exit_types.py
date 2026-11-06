"""Single source of truth for backtest trade exit-type (outcome) labels.

``Trade.exit_type`` records HOW a position closed. Centralised here so the exit
helpers, the attribution breakdown, chart markers, and tests share one vocabulary
instead of scattered magic strings.

WHY this is distinct from :class:`ExitStrategy`:
- ``ExitStrategy`` is the *requested* exit policy (``fixed_holding``, ``atr_based``...).
- ``exit_type`` is the *realised* outcome of a single trade. One strategy yields
  several outcomes -- e.g. ``atr_based`` -> ``take_profit`` | ``stop_loss`` | ``timeout``.

WHY ``timeout`` is separate from ``signal`` (the load-bearing distinction):
- ``signal`` = the strategy closed the position deliberately at that bar
  (FIXED_HOLDING reaching its N-candle horizon -- the intended exit).
- ``timeout`` = a BARRIER strategy (fixed_tpsl / risk_reward / atr_based /
  dynamic_tpsl / trailing_stop / min_profit) was FORCE-CLOSED at the
  ``holding_periods`` deadline because no barrier triggered. Labelling both
  ``signal`` hid how often barrier exits never fired (the deadline starved them).
"""

from __future__ import annotations

from typing import Final

from src.shared.constants.backtest_leverage import BACKTEST_EXIT_TYPE_LIQUIDATION

#: Strategy closed the position deliberately at this bar (FIXED_HOLDING horizon).
BACKTEST_EXIT_TYPE_SIGNAL: Final[str] = "signal"
#: Stop-loss level touched.
BACKTEST_EXIT_TYPE_STOP_LOSS: Final[str] = "stop_loss"
#: Take-profit level touched.
BACKTEST_EXIT_TYPE_TAKE_PROFIT: Final[str] = "take_profit"
#: Trailing stop locked in after activation.
BACKTEST_EXIT_TYPE_TRAILING_STOP: Final[str] = "trailing_stop"
#: MIN_PROFIT_AFTER_FEES net-positive exit.
BACKTEST_EXIT_TYPE_MIN_PROFIT: Final[str] = "min_profit"
#: RAW_SIGNAL opposite-direction signal closed the position.
BACKTEST_EXIT_TYPE_OPPOSITE_SIGNAL: Final[str] = "opposite_signal"
#: Barrier strategy force-closed at the holding_periods deadline (no barrier hit).
BACKTEST_EXIT_TYPE_TIMEOUT: Final[str] = "timeout"

#: Every recognised exit-type label. ``liquidation`` is owned by ``backtest_leverage``
#: and re-exported here so the breakdown vocabulary has a single complete set.
ALL_BACKTEST_EXIT_TYPES: Final[frozenset[str]] = frozenset(
    {
        BACKTEST_EXIT_TYPE_SIGNAL,
        BACKTEST_EXIT_TYPE_STOP_LOSS,
        BACKTEST_EXIT_TYPE_TAKE_PROFIT,
        BACKTEST_EXIT_TYPE_TRAILING_STOP,
        BACKTEST_EXIT_TYPE_MIN_PROFIT,
        BACKTEST_EXIT_TYPE_OPPOSITE_SIGNAL,
        BACKTEST_EXIT_TYPE_TIMEOUT,
        BACKTEST_EXIT_TYPE_LIQUIDATION,
    }
)

__all__ = [
    "ALL_BACKTEST_EXIT_TYPES",
    "BACKTEST_EXIT_TYPE_LIQUIDATION",
    "BACKTEST_EXIT_TYPE_MIN_PROFIT",
    "BACKTEST_EXIT_TYPE_OPPOSITE_SIGNAL",
    "BACKTEST_EXIT_TYPE_SIGNAL",
    "BACKTEST_EXIT_TYPE_STOP_LOSS",
    "BACKTEST_EXIT_TYPE_TAKE_PROFIT",
    "BACKTEST_EXIT_TYPE_TIMEOUT",
    "BACKTEST_EXIT_TYPE_TRAILING_STOP",
]
