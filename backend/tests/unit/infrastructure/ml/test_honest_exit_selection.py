"""TDD: pure honest-exit selection (deflation + tiered gate + best-exit pick).

Shared SoT for the research evaluator AND training Step 8 — given per-exit backtest results,
pick the best exit that clears the min-trades floor and report its deflated Sharpe + tier.
A Sharpe on too-few trades is not a measurement and must be excluded from the pick.
"""

from __future__ import annotations

from src.infrastructure.ml.honest_exit_selection import (
    ExitCellResult,
    HonestExitVerdict,
    resolve_honest_tier,
    select_honest_exit,
)
from src.shared.constants.backtest import EXPLORATORY_OOS_MIN_DEFLATED_SHARPE

_GATE_KW = {"oos_days": 120, "timeframe": "1d", "oos_start": "2026-03-02", "oos_end": "2026-07-06"}
_KNOWN_TIERS = {"T4 CERTIFICATION", "T3 RESEARCH", "T2 EXPLORATORY", "T1 SCOUT", "FAIL", "NO_DATA"}


def _cell(label: str, sharpe: float, net: float, trades: int, pf: float = 1.5) -> ExitCellResult:
    return ExitCellResult(label=label, sharpe=sharpe, net=net, trades=trades, profit_factor=pf)


def test_no_valid_cells_returns_no_data() -> None:
    v = select_honest_exit([], **_GATE_KW)
    assert isinstance(v, HonestExitVerdict)
    assert v.tier == "NO_DATA"
    assert v.best_label is None


def test_all_below_min_trades_returns_no_data() -> None:
    cells = [_cell("a", 5.0, 0.1, 3), _cell("b", 4.0, 0.1, 5)]
    v = select_honest_exit(cells, min_trades=10, **_GATE_KW)
    assert v.tier == "NO_DATA"
    assert v.n_valid == 0


def test_picks_highest_sharpe_among_valid() -> None:
    cells = [_cell("lo", 0.5, 0.05, 50), _cell("hi", 1.4, 0.20, 60), _cell("mid", 1.0, 0.1, 40)]
    v = select_honest_exit(cells, min_trades=10, **_GATE_KW)
    assert v.best_label == "hi"
    assert v.best_trades == 60
    assert v.n_valid == 3
    assert v.n_trials == 3
    assert v.deflated_sharpe_prob is not None
    assert 0.0 <= v.deflated_sharpe_prob <= 1.0
    assert v.tier in _KNOWN_TIERS


def test_min_trades_excludes_high_sharpe_thin_cell() -> None:
    # A 2-trade Sharpe of 99 is noise, not an edge — must NOT be chosen.
    cells = [_cell("thin_but_huge", 99.0, 0.9, 2), _cell("real", 1.2, 0.15, 80)]
    v = select_honest_exit(cells, min_trades=10, **_GATE_KW)
    assert v.best_label == "real"
    assert v.n_valid == 1


def test_deflation_penalizes_many_trials() -> None:
    # Same observed best Sharpe, but a wide spread of many trials deflates harder than one clean trial.
    many = [_cell(f"c{i}", 0.2 * i, 0.05, 40) for i in range(1, 12)]  # spread 0.2..2.2
    few = [_cell("only", 2.2, 0.05, 40), _cell("only2", 2.0, 0.05, 40)]
    v_many = select_honest_exit(many, min_trades=10, **_GATE_KW)
    v_few = select_honest_exit(few, min_trades=10, **_GATE_KW)
    assert v_many.best_sharpe == v_few.best_sharpe == 2.2
    assert v_many.deflated_sharpe_prob <= v_few.deflated_sharpe_prob


def test_tier_bands_ordered_strongest_first() -> None:
    assert resolve_honest_tier(deflated_sharpe_prob=0.5, scout_pass=True, research_pass=True, certification_pass=True) == "T4 CERTIFICATION"
    assert resolve_honest_tier(deflated_sharpe_prob=0.99, scout_pass=True, research_pass=True, certification_pass=False) == "T3 RESEARCH"
    # BNB 1d v4 case: 0.825 clears the 0.80 nice-to-have bar -> exploratory (paper-only)
    assert resolve_honest_tier(deflated_sharpe_prob=0.825, scout_pass=True, research_pass=False, certification_pass=False) == "T2 EXPLORATORY"
    assert resolve_honest_tier(deflated_sharpe_prob=0.70, scout_pass=True, research_pass=False, certification_pass=False) == "T1 SCOUT"
    assert resolve_honest_tier(deflated_sharpe_prob=0.70, scout_pass=False, research_pass=False, certification_pass=False) == "FAIL"


def test_exploratory_bar_is_configurable() -> None:
    # Raise the nice-to-have bar to 0.90 -> 0.825 no longer qualifies (falls back to SCOUT).
    assert (
        resolve_honest_tier(deflated_sharpe_prob=0.825, scout_pass=True, research_pass=False, certification_pass=False, exploratory_dsr=0.90)
        == "T1 SCOUT"
    )
    assert EXPLORATORY_OOS_MIN_DEFLATED_SHARPE == 0.80
