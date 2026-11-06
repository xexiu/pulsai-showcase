"""Tests for the backtest exit-type SoT constants (``backtest_exit_types``)."""

from __future__ import annotations

from src.shared.constants.backtest_exit_types import (
    ALL_BACKTEST_EXIT_TYPES,
    BACKTEST_EXIT_TYPE_LIQUIDATION,
    BACKTEST_EXIT_TYPE_SIGNAL,
    BACKTEST_EXIT_TYPE_TIMEOUT,
)

# Realised exit outcomes: signal, stop_loss, take_profit, trailing_stop,
# min_profit, opposite_signal, timeout, liquidation.
EXPECTED_EXIT_TYPE_COUNT = 8


def test_all_exit_types_is_complete_and_deduplicated() -> None:
    """Every label distinct -> a copy-paste duplicate value would shrink the set."""
    assert len(ALL_BACKTEST_EXIT_TYPES) == EXPECTED_EXIT_TYPE_COUNT


def test_timeout_is_distinct_from_signal() -> None:
    """The load-bearing distinction: a forced deadline exit is not an intended signal exit."""
    assert BACKTEST_EXIT_TYPE_TIMEOUT != BACKTEST_EXIT_TYPE_SIGNAL
    assert BACKTEST_EXIT_TYPE_TIMEOUT in ALL_BACKTEST_EXIT_TYPES
    assert BACKTEST_EXIT_TYPE_SIGNAL in ALL_BACKTEST_EXIT_TYPES


def test_liquidation_reexport_matches_leverage_owner() -> None:
    """Single value source: the re-export must not drift from ``backtest_leverage``."""
    from src.shared.constants.backtest_leverage import (
        BACKTEST_EXIT_TYPE_LIQUIDATION as LEVERAGE_LIQUIDATION,
    )

    assert LEVERAGE_LIQUIDATION == BACKTEST_EXIT_TYPE_LIQUIDATION
    assert BACKTEST_EXIT_TYPE_LIQUIDATION in ALL_BACKTEST_EXIT_TYPES
