"""Accuracy must measure TRADING skill, so it must know which actions are trades.

WHY THIS EXISTS (measured 2026-08-06): signal accuracy counted HOLD. HOLD was 48% of all
evaluated signals and, through a separate bug, was hardcoded "correct" — so the metric
reported 98.7% where real actionable skill was 46.9%. That is the difference between "healthy"
and below the 50% CRITICAL floor that fires hourly retraining and feeds rollback conditions.

The tuple ("BUY", "SELL") was inlined in Signal.is_actionable and re-derived ad hoc elsewhere.
`SignalAction.actionable()` is now the single source of truth.
"""

from __future__ import annotations

from src.domain.enums import SignalAction


def test_actionable_is_buy_and_sell_only() -> None:
    assert SignalAction.actionable() == frozenset({SignalAction.BUY, SignalAction.SELL})


def test_hold_is_not_actionable() -> None:
    """HOLD is a prediction, never a position — it has no capital consequence."""
    assert SignalAction.HOLD not in SignalAction.actionable()


def test_plain_strings_match_so_db_rows_work() -> None:
    """Rows come back as plain strings; StrEnum membership must still hold.

    If this broke, the accuracy query would silently match nothing and report 0 signals.
    """
    assert "BUY" in SignalAction.actionable()
    assert "SELL" in SignalAction.actionable()
    assert "HOLD" not in SignalAction.actionable()


def test_every_action_is_either_actionable_or_hold() -> None:
    """No third category may appear without this metric being reconsidered."""
    actionable = SignalAction.actionable()
    for action in SignalAction:
        assert (action in actionable) != (action is SignalAction.HOLD)
