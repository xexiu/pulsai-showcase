"""Pure honest-exit selection: pick the best exit + report its deflated Sharpe + research tier.

SoT for BOTH the research evaluator (``src/research/honest_exit_grid_eval.py``) and training
Step 8's honest sweep. Given per-exit backtest results, keep only cells that clear the min-trades
floor (a Sharpe on too-few trades is not a measurement), pick the highest-Sharpe survivor, then
deflate it by the number of exits tried (``n_trials`` = valid cells) and map to a tier.

Tier bands (deflated-Sharpe probability):
  - **T4 CERTIFICATION** — full research gate (200+ trades) + DSR >= 0.95.
  - **T3 RESEARCH** — DSR >= 0.95 (research bar); real-capital-eligible only after forward validation.
  - **T2 EXPLORATORY** — DSR >= ``exploratory_dsr`` (default 0.80): the "nice-to-have" band, PAPER-ONLY.
  - **T1 SCOUT** — profitable (net>0 & PF>1) but below the exploratory bar (multiple-testing luck).
  - **FAIL** / **NO_DATA**.

No I/O — trivially unit-testable.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from src.shared.constants.backtest import EXPLORATORY_OOS_MIN_DEFLATED_SHARPE, EXPLORATORY_OOS_MIN_TRADES
from src.shared.math.backtest_validation_statistics import honest_deflated_sharpe
from src.shared.math.oos_window import OosWindow, evaluate_oos_window_gate

_MIN_TRADES_DEFAULT = EXPLORATORY_OOS_MIN_TRADES
"""Pre-filter floor: BOUND to the weakest tier's own floor, not a second copy of the number.

Was a bare `10`, which is the same value `EXPLORATORY_OOS_MIN_TRADES` already carries. Two
independent 10s is the defect, not the 10: a pre-filter STRICTER than the weakest tier drops cells
the gate below would have classified T1/T2, and nothing here would have said so -- the cells simply
would not appear. Bound, the two can no longer disagree.

STILL OPEN, and deliberately not changed here: whether this floor should also SCALE with the OOS
window. It is a fluke filter as well as a tier floor, and those two jobs disagree by timeframe --
10 trades over a 90-day 1d window is ~11% of bars (a real book), while 10 trades over the same
window at 5m is 10 of ~25,920 bars (a Sharpe that wins `max()` by luck and inflates `n_trials`).
Changing it is a GATE change, and `.claude/rules/investigate-before-changing-a-gate.md` requires the
corpus counts FIRST: how many cells in the existing exit-grid artifacts sit between the flat 10 and
a window-scaled floor, per timeframe. Editing it on the argument alone is exactly the instinct-edit
that rule was written after. Tracked, not deferred."""


@dataclass(frozen=True)
class ExitCellResult:
    """One exit cell's OOS backtest outcome (``sharpe=None`` => the cell errored / no result)."""

    label: str
    sharpe: float | None
    net: float
    trades: int
    profit_factor: float


@dataclass(frozen=True)
class HonestExitVerdict:
    """Best surviving exit + its honest metrics. ``tier`` in {T4/T3/T2/T1/FAIL/NO_DATA}."""

    best_label: str | None
    best_sharpe: float | None
    best_net: float | None
    best_trades: int | None
    deflated_sharpe_prob: float | None
    n_trials: int
    n_valid: int
    tier: str
    rank_pool_thin: bool = False
    """True when NO admitted cell cleared the ranking floor, so the winner came from thin cells.

    Reported rather than suppressed: a window where nothing is thick still deserves a verdict,
    but a reader must be able to tell that verdict apart from one chosen among real books. An
    unflagged thin winner is the flattering default -- indistinguishable from a measured result.
    """


def resolve_honest_tier(
    *,
    deflated_sharpe_prob: float | None,
    scout_pass: bool,
    research_pass: bool,
    certification_pass: bool,
    exploratory_dsr: float = EXPLORATORY_OOS_MIN_DEFLATED_SHARPE,
) -> str:
    """Map the gate verdict + deflated Sharpe to a tier.

    T2 EXPLORATORY (>= ``exploratory_dsr``, default 0.80) is the "nice-to-have" / paper-only band
    between SCOUT (merely profitable) and RESEARCH (>= 0.95). Ordered strongest-first.
    """
    if certification_pass:
        return "T4 CERTIFICATION"
    if research_pass:
        return "T3 RESEARCH"
    if deflated_sharpe_prob is not None and deflated_sharpe_prob >= exploratory_dsr:
        return "T2 EXPLORATORY"
    if scout_pass:
        return "T1 SCOUT"
    return "FAIL"


def select_honest_exit(
    cells: list[ExitCellResult],
    *,
    oos_days: int,
    timeframe: str,
    oos_start: str,
    oos_end: str,
    min_trades: int = _MIN_TRADES_DEFAULT,
    rank_min_trades: int | None = None,
    exploratory_dsr: float = EXPLORATORY_OOS_MIN_DEFLATED_SHARPE,
) -> HonestExitVerdict:
    """Pick the best min-trades-clearing exit; deflate by n_trials (valid cells); map the tier.

    ``min_trades`` is ADMISSION -- may this cell be tiered at all. ``rank_min_trades`` is a
    separate, optional question: may it WIN. They were one number, and the corpus says they
    should not be.

    MEASURED over 347 cert artifacts with a usable window (~1.46M graded cells): 243,767 cells
    clear the flat floor of 10 and would not clear `resolve_research_min_trades(window_bars)`,
    and the share is asymmetric by timeframe -- 3.3% on 6h against 31.4% on 12h. Those cells feed
    BOTH the `max()` below and the `n_trials` deflation count, so a 10-trade cell out of 11,700
    bars can win a sweep outright while inflating the denominator meant to price exactly that
    luck.

    Raising ADMISSION instead was considered and rejected against the same data: 10 is the T1/T2
    tier's own bar, so a stricter pre-filter deletes cells the gate would have classified -- on
    1h, 3,316 of 14,983. Admission stays flat; only the ranking narrows.

    ``rank_min_trades=None`` keeps every existing caller byte-identical.
    """
    valid = [c for c in cells if c.sharpe is not None and c.trades >= min_trades]
    if not valid:
        return HonestExitVerdict(None, None, None, None, None, len(cells), 0, "NO_DATA")

    # n_trials counts every cell that COMPETED, thin ones included: they were tried, so they
    # price the search. Deflating by the thick pool alone would flatter the DSR by hiding arms.
    trial_sharpes: list[float] = [s for c in valid if (s := c.sharpe) is not None]
    rankable = [c for c in valid if c.trades >= rank_min_trades] if rank_min_trades else valid
    rank_pool_thin = not rankable
    if rank_pool_thin:
        rankable = valid
    best = max(rankable, key=lambda c: c.sharpe if c.sharpe is not None else float("-inf"))
    best_sharpe = best.sharpe if best.sharpe is not None else 0.0

    deflated = honest_deflated_sharpe(best_sharpe, trial_sharpes, n_observations=oos_days)
    gate = evaluate_oos_window_gate(
        net=float(best.net),
        profit_factor=float(best.profit_factor),
        num_trades=int(best.trades),
        observed_sharpe=best_sharpe,
        n_trials=len(trial_sharpes),
        trial_sharpe_std=statistics.pstdev(trial_sharpes) if len(trial_sharpes) > 1 else 0.0,
        window=OosWindow(timeframe=timeframe, start=oos_start, end=oos_end),
    )
    tier = resolve_honest_tier(
        deflated_sharpe_prob=deflated,
        scout_pass=bool(getattr(gate, "scout_pass", False)),
        research_pass=bool(getattr(gate, "research_pass", False)),
        certification_pass=bool(getattr(gate, "certification_pass", False)),
        exploratory_dsr=exploratory_dsr,
    )
    return HonestExitVerdict(
        best_label=best.label,
        best_sharpe=best_sharpe,
        best_net=float(best.net),
        best_trades=int(best.trades),
        deflated_sharpe_prob=deflated,
        n_trials=len(trial_sharpes),
        n_valid=len(valid),
        tier=tier,
        rank_pool_thin=rank_pool_thin,
    )
