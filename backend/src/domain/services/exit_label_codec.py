"""Read and write exit-grid labels. `tpsl_8_3` means SL=8, TP=3 — the name lies.

WHY THIS MODULE EXISTS, measured 2026-08-12. Replicating `1d lightgbm v41`'s cert cell through the
prod backtester, the label `tpsl_8_3` was read as take-profit 8 / stop-loss 3 — the order the NAME
implies:

    wrong decode (TP=8, SL=3)   -6.0%   73 trades   win_rate 34.2%
    right decode (SL=8, TP=3)  +18.0%   71 trades   win_rate 74.6%   <- the cert, digit-for-digit

From that single inversion came a published conclusion that the cert engine "cannot be trusted to
predict prod behaviour for ANY book". It was a false alarm, and an expensive one: two of the three
numbers (71≈73 trades, -39.2% vs -38.4% DD) had already agreed, which is the signature of a decode
error rather than an engine bug.

THE ORDER IS NOT A BUG — IT IS CONSISTENT. All four construction sites agree:

    scout_exit_grid_kernels.py:41          f"tpsl_{sl:g}_{tp:g}"
    rl_edge/experiment.py:1146             f"tpsl_{sl:g}_{tp:g}_h{hold}"
    infrastructure/ml/exit_grid.py:59      f"tpsl_{sl_i:g}_{tp_i:g}"
    btc_meta_walkforward_matrix.py         ExitKernel(label, strategy, stop_loss_pct, take_profit_pct, ...)

**The NAME is the defect**: `tpsl` reads take-profit-then-stop-loss and encodes the reverse.
Renaming the prefix would invalidate every artifact on disk and every historical result keyed by
it, so the fix is this codec — one place that knows the order, with the surprise stated where it
is used instead of rediscovered.

RETURNS None FOR NON-GRID EXITS (`dyn_tpsl_x3`, `trail_1_1`, `breakeven`, `hold`). A guessed lever
is worse than a missing one: it silently runs a different book and reports the result under the
original book's name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

#: The exit families that attach a STOP AT ENTRY -- fixed SL/TP, trailing, ATR, R-multiple, dynamic SL/TP and the thin
#: wick stop. ONE home (moved from the 5m lab's precommit_grade, 2026-10-09): the owner's product spec and the money
#: grade's "risk-managed sizing" (stop at entry + a fraction of equity at risk) both read it. `hold_N`, `breakeven`
#: and the like carry no stop.
STOP_AT_ENTRY_EXIT_PREFIXES: Final[tuple[str, ...]] = ("tpsl_", "trail_", "atr_", "rr_", "dyn_tpsl_", "thin_")


def exit_has_stop_at_entry(label: object) -> bool:
    """Does the exit-grid ``label`` attach a stop at entry?"""
    return str(label or "").startswith(STOP_AT_ENTRY_EXIT_PREFIXES)


#: `tpsl_<stop_loss>_<take_profit>`, `.` written as `p` to stay filesystem-safe.
_TPSL_LABEL: Final = re.compile(r"^tpsl_(\d+(?:p\d+)?)_(\d+(?:p\d+)?)$")


@dataclass(frozen=True, slots=True)
class ExitLevels:
    """Percent levels for a fixed-TP/SL exit.

    Named fields on purpose: a tuple would let a caller re-introduce the very swap this module
    exists to prevent.
    """

    stop_loss_pct: float
    take_profit_pct: float


def _num(token: str) -> float:
    return float(token.replace("p", "."))


def decode_exit_label(label: str | None) -> ExitLevels | None:
    """`tpsl_8_3` -> ExitLevels(stop_loss_pct=8.0, take_profit_pct=3.0). STOP-LOSS FIRST.

    None when the label is not a fixed-TP/SL grid cell, so callers must handle non-grid exits
    explicitly rather than guessing levels for `trail_1_1` or `dyn_tpsl_x3`.
    """
    match = _TPSL_LABEL.match((label or "").strip())
    if match is None:
        return None
    return ExitLevels(stop_loss_pct=_num(match.group(1)), take_profit_pct=_num(match.group(2)))


def encode_tpsl_label(stop_loss_pct: float, take_profit_pct: float) -> str:
    """Build the canonical label. Byte-identical to the existing grid writers.

    Keyword-friendly on purpose — `encode_tpsl_label(stop_loss_pct=8, take_profit_pct=3)` reads
    unambiguously, which `f"tpsl_{a}_{b}"` at four separate call sites does not.
    """
    return f"tpsl_{stop_loss_pct:g}_{take_profit_pct:g}".replace(".", "p")
