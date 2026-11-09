"""A drawdown must say WHICH basis produced it, because the basis is conditional.

MEASURED 2026-08-22 across 64 cert files / 153 lane rows: `drawdown_basis` is present **0 times**.
So no MTM claim anywhere in the corpus is verifiable from its own artifact.

That would be a documentation nit if the basis were fixed. It is not — `calculate_metrics` picks
it at runtime:

    mtm_drawdown = mark_to_market_max_drawdown(trades, low, high, starting_balance, leverage=leverage)
    if mtm_drawdown is not None:
        max_drawdown = mtm_drawdown

and the surrounding comment states the consequence outright: *"`leverage` stays None for every
caller that has not opted in, so the drawdown is byte-identical"* to the closed-trade figure. So
two certs can print `max_drawdown` in the same column meaning two different measurements, and the
reader cannot tell which — while `ml-gate-leverage-capital-cert.md` requires the HONEST MTM
drawdown beside any leveraged number.

Recording the basis is what makes the rule checkable instead of assumed.
"""

from __future__ import annotations

import pytest

from src.infrastructure.ml.backtester_metrics import calculate_metrics
from src.shared.constants.backtest import (
    DRAWDOWN_BASIS_BAR_CLOSE,
    DRAWDOWN_BASIS_MARK_TO_MARKET,
)

#: The required positional contract, kept in one place so a signature change breaks it once.
BASE_KWARGS = {
    "total_fees": 0.0,
    "total_slippage": 0.0,
    "position_size": 10_000.0,
    "holding_periods": 4,
    "timeframe": "1d",
    "annualization_factor": 365.0,
    "initial_capital": 10_000.0,
}


def _metrics(trades: list, **extra: object):
    return calculate_metrics(trades, **BASE_KWARGS, **extra)  # type: ignore[arg-type]


class TestTheBasisIsRecorded:
    def test_an_unlevered_run_declares_bar_close(self) -> None:
        assert _metrics([]).drawdown_basis == DRAWDOWN_BASIS_BAR_CLOSE

    def test_the_basis_is_never_empty(self) -> None:
        """An absent label is what made 153 lane rows unreadable."""
        assert _metrics([]).drawdown_basis

    def test_the_two_bases_are_distinct_labels(self) -> None:
        assert DRAWDOWN_BASIS_BAR_CLOSE != DRAWDOWN_BASIS_MARK_TO_MARKET


class TestTheDrawdownItselfIsUnchanged:
    def test_recording_the_basis_does_not_move_the_number(self) -> None:
        """Additive only — this must not shift a single existing figure."""
        assert _metrics([]).max_drawdown == pytest.approx(0.0)

    def test_an_empty_book_still_carries_a_basis(self) -> None:
        result = _metrics([])

        assert result.drawdown_basis == DRAWDOWN_BASIS_BAR_CLOSE
        assert result.num_trades == 0
