"""The out-of-sample window a research gate grades -- one value, not three loose arguments.

IMPORTERS/CALLERS: the research validators that grade a cell with the tiered OOS gate
(``src/infrastructure/ml/honest_exit_selection.py``, ``src/research/oos_tiered_gate_row.py``, and the
rest of the lab as it migrates) and ``tests/unit/shared/math/test_oos_window.py``.
AFFECTED API: none. Adds ``OosWindow`` and ``evaluate_oos_window_gate``; nothing existing moves.
DATA SCHEMAS: none.

WHY A TYPE (P1-9g). ``evaluate_oos_tiered_gate`` took eleven arguments and carried a PLR0913 noqa
for it (it is deleted: its body lives here). Measured with ``ast`` over every call in apps/api: 49 calls, and all 49 pass the same nine --
``timeframe``, ``oos_start`` and ``oos_end`` among them, always together, because they are ONE fact:
which bars were out of sample (``estimate_oos_bars`` consumes exactly those three). ``min_deflated_sharpe``
is passed at 0 of 49, so this door grades at the default DSR floor and does not offer it.
One value for the window plus that unused knob gone brings the gate to eight, within ruff's max-args (8).

WHERE THE LOGIC LIVES. The migration is complete: every lab and product caller grades through this door, so the
eleven-argument function and its noqa are gone and this module owns the tiered grading.

REUSE-AUDIT: considered ``src/research/oos_classic_adx_macd_walkforward.py::Window`` and
``src/research/elder_rsi_strategy_pulse.py::Window`` -- lab-local, and src/shared may not import the lab.
Considered ``src/infrastructure/ml/rolling_origin.py::RollingWindow`` -- a rolling train/test split, not a
graded calendar span. No shared OOS-window value exists. Pattern row: a DDD Value Object
(``docs/04-structural/DDD_PATTERNS.md`` section Value Objects) as a frozen dataclass; the Builder row's
anti-fit in ``docs/04-structural/ARCHITECTURE_PATTERNS.md`` section 1 -- "a dataclass already says it" --
is why there is no builder, factory or behaviour here.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.constants.backtest import BACKTEST_VALIDATION_MIN_TRADES
from src.shared.math.backtest_validation_statistics import (
    OosTieredGateVerdict,
    estimate_oos_bars,
    evaluate_backtest_validation,
    resolve_research_min_trades,
)


@dataclass(frozen=True)
class OosWindow:
    """Bar timeframe (``"4h"``, ``"1d"``, ...) and calendar span; dates are ``YYYY-MM-DD`` (first 10 chars read)."""

    timeframe: str
    start: str
    end: str


def evaluate_oos_window_gate(
    *,
    net: float,
    profit_factor: float,
    num_trades: int,
    observed_sharpe: float,
    n_trials: int,
    trial_sharpe_std: float,
    window: OosWindow,
    research_min_trades_override: int | None = None,
) -> OosTieredGateVerdict:
    """Scout / window-scaled research / certification tiers for one OOS cell, at the default DSR floor.

    The window sets the research trade floor (``resolve_research_min_trades`` of its bar count), which
    ``research_min_trades_override`` replaces when given; certification always uses the flat floor.
    """
    oos_bars = estimate_oos_bars(timeframe=window.timeframe, start_date=window.start, end_date=window.end)
    min_research = int(research_min_trades_override) if research_min_trades_override is not None else resolve_research_min_trades(oos_bars)
    min_cert = BACKTEST_VALIDATION_MIN_TRADES

    net_positive = net > 0
    pf_above_one = profit_factor > 1.0
    scout_pass = net_positive and pf_above_one

    research_validation = evaluate_backtest_validation(
        num_trades=num_trades,
        observed_sharpe=observed_sharpe,
        n_trials=n_trials,
        trial_sharpe_std=trial_sharpe_std,
        min_trades=min_research,
    )
    certification_validation = evaluate_backtest_validation(
        num_trades=num_trades,
        observed_sharpe=observed_sharpe,
        n_trials=n_trials,
        trial_sharpe_std=trial_sharpe_std,
        min_trades=min_cert,
    )

    return OosTieredGateVerdict(
        scout_pass=scout_pass,
        research_pass=scout_pass and research_validation.passed,
        certification_pass=scout_pass and certification_validation.passed,
        oos_bars=oos_bars,
        min_trades_research=min_research,
        min_trades_certification=min_cert,
        net_positive=net_positive,
        pf_above_one=pf_above_one,
        num_trades=int(num_trades),
        deflated_sharpe=certification_validation.deflated_sharpe,
        research_validation=research_validation,
        certification_validation=certification_validation,
    )


__all__ = ["OosWindow", "evaluate_oos_window_gate"]
