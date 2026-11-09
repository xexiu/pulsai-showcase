from __future__ import annotations

import polars as pl

from src.infrastructure.ml.backtester_apply_trade_levels import apply_trade_levels_for_signal_bar
from src.infrastructure.ml.backtester_types import ExitStrategy, Trade


class _StubBacktester:
    exit_strategy = ExitStrategy.FIXED_HOLDING

    def _dynamic_entry_metadata(
        self,
        entry_price: float,
        direction: int,
        df: pl.DataFrame,
        entry_candle: int,
    ) -> tuple[float | None, float | None, str | None]:
        return (95.0, 108.0, "high")

    def _compute_tpsl_levels(
        self,
        entry_price: float,
        direction: int,
        df: pl.DataFrame,
        signal_bar: int,
    ) -> tuple[float | None, float | None]:
        return (None, None)


def test_apply_trade_levels_falls_back_to_dynamic_metadata_when_fixed_levels_missing() -> None:
    backtester = _StubBacktester()
    trade = Trade(
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        size=100.0,
        entry_fee=0.1,
        exit_fee=0.1,
        slippage_cost=0.05,
        gross_pnl=1.0,
        net_pnl=0.75,
    )
    df = pl.DataFrame({"timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"]})

    apply_trade_levels_for_signal_bar(backtester, trade, df, signal_bar_index=0)

    assert trade.stop_loss_price == 95.0
    assert trade.take_profit_price == 108.0
    assert trade.dynamic_volatility_regime == "high"


def test_apply_trade_levels_derives_min_tp_1r_and_full_tp_using_trading_bots_rules() -> None:
    backtester = _StubBacktester()
    trade = Trade(
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        size=100.0,
        entry_fee=0.1,
        exit_fee=0.1,
        slippage_cost=0.05,
        gross_pnl=1.0,
        net_pnl=0.75,
    )
    df = pl.DataFrame(
        {
            "timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"],
            "channel_5m_upper": [106.0, 106.0],
            "volatility_margin": [1.5, 1.5],
        }
    )

    apply_trade_levels_for_signal_bar(backtester, trade, df, signal_bar_index=0)

    assert trade.stop_loss_price == 95.0
    assert trade.take_profit_price == 108.0
    # min_tp = min(tp(108), channel_upper(106))
    assert trade.min_tp_price == 106.0
    # tp_1r = entry + 1R = 100 + (100 - 95)
    assert trade.tp_1r_price == 105.0
    # full_tp = max(tp(108), channel_upper(106))
    assert trade.full_tp_price == 108.0
