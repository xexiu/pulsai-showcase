"""
Behaviour tests for backtest exit-type attribution + the timeout relabel.

WHY: a barrier strategy (TP/SL/ATR/trailing/min-profit) that never triggers is
force-closed at the holding deadline. That exit is now labelled ``timeout`` (not
``signal``) and aggregated into ``BacktestResult.exit_type_counts`` so deadline
starvation is visible instead of hidden behind net metrics.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from src.infrastructure.ml.backtester_exit_common import (
    exit_on_first_hit,
    timeout_signal_exit,
)
from src.infrastructure.ml.backtester_metrics import calculate_metrics, empty_result
from src.infrastructure.ml.backtester_raw_signal_exit import find_opposite_signal_exit
from src.infrastructure.ml.backtester_types import Trade
from src.shared.constants.backtest_exit_types import (
    BACKTEST_EXIT_TYPE_OPPOSITE_SIGNAL,
    BACKTEST_EXIT_TYPE_STOP_LOSS,
    BACKTEST_EXIT_TYPE_TAKE_PROFIT,
    BACKTEST_EXIT_TYPE_TIMEOUT,
)


def _trade(exit_type: str, net_pnl: float) -> Trade:
    """Minimal Trade with a chosen exit_type and pnl (size 1000 for stable returns)."""
    return Trade(
        entry_price=100.0,
        exit_price=100.0 + net_pnl / 10.0,
        direction=1,
        size=1000.0,
        entry_fee=1.0,
        exit_fee=1.0,
        slippage_cost=0.5,
        gross_pnl=net_pnl + 2.5,
        net_pnl=net_pnl,
        exit_type=exit_type,
    )


class TestTimeoutRelabel:
    """Barrier-deadline force-close is labelled ``timeout``, not ``signal``."""

    def test_timeout_signal_exit_labels_timeout(self) -> None:
        open_prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        candle, price, exit_type, _stop_fill = timeout_signal_exit(max_exit_candle=4, open_prices=open_prices, df_len=len(open_prices))
        assert exit_type == BACKTEST_EXIT_TYPE_TIMEOUT
        assert candle == 4
        assert price == 104.0

    def test_raw_signal_timeout_fallback_labels_timeout(self) -> None:
        # No opposite (-1) signal within the holding window -> deadline timeout.
        signals = np.array([1, 1, 1, 1, 1, 1])
        open_prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        result = find_opposite_signal_exit(entry_candle=1, signals=signals, open_prices=open_prices, direction=1, df_len=6, holding_periods=3)
        assert result is not None
        _, _, exit_type = result
        assert exit_type == BACKTEST_EXIT_TYPE_TIMEOUT

    def test_raw_signal_opposite_labels_opposite_signal(self) -> None:
        signals = np.array([1, 1, -1, 1, 1, 1])  # opposite (-1) at index 2
        open_prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        result = find_opposite_signal_exit(entry_candle=1, signals=signals, open_prices=open_prices, direction=1, df_len=6, holding_periods=5)
        assert result is not None
        _, _, exit_type = result
        assert exit_type == BACKTEST_EXIT_TYPE_OPPOSITE_SIGNAL


class TestExitOnFirstHitLabels:
    """SL/TP outcomes carry the SoT labels."""

    @staticmethod
    def _df(highs: list[float], lows: list[float]) -> pl.DataFrame:
        return pl.DataFrame({"open": [100.0] * len(highs), "high": highs, "low": lows})  # every bar opens at the entry

    def test_take_profit_label(self) -> None:
        df = self._df(highs=[101.0, 104.0, 105.0], lows=[99.5, 100.0, 100.0])
        result = exit_on_first_hit(entry_candle=0, direction=1, df=df, max_exit_candle=2, sl_level=98.0, tp_level=103.0)
        assert result is not None
        _, _, exit_type, _stop_fill = result
        assert exit_type == BACKTEST_EXIT_TYPE_TAKE_PROFIT

    def test_stop_loss_label(self) -> None:
        df = self._df(highs=[100.5, 100.5, 100.5], lows=[99.5, 97.0, 96.0])
        result = exit_on_first_hit(entry_candle=0, direction=1, df=df, max_exit_candle=2, sl_level=98.0, tp_level=110.0)
        assert result is not None
        _, _, exit_type, _stop_fill = result
        assert exit_type == BACKTEST_EXIT_TYPE_STOP_LOSS


class TestExitTypeAttribution:
    """``calculate_metrics`` aggregates the realised exit_type of every trade."""

    def test_counts_exit_types_across_trades(self) -> None:
        trades = [
            _trade(BACKTEST_EXIT_TYPE_TAKE_PROFIT, 30.0),
            _trade(BACKTEST_EXIT_TYPE_TAKE_PROFIT, 25.0),
            _trade(BACKTEST_EXIT_TYPE_STOP_LOSS, -20.0),
            _trade(BACKTEST_EXIT_TYPE_TIMEOUT, -5.0),
        ]
        result = calculate_metrics(
            trades=trades,
            total_fees=8.0,
            total_slippage=2.0,
            position_size=1000.0,
            holding_periods=4,
            timeframe="1h",
            annualization_factor=1.0,
        )
        assert result.exit_type_counts == {
            BACKTEST_EXIT_TYPE_TAKE_PROFIT: 2,
            BACKTEST_EXIT_TYPE_STOP_LOSS: 1,
            BACKTEST_EXIT_TYPE_TIMEOUT: 1,
        }

    def test_empty_result_has_no_exit_type_counts(self) -> None:
        assert empty_result(initial_capital=10_000.0).exit_type_counts == {}
