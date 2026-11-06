"""CERT capital must match /backtest/run bankruptcy realism (no fantasy post-ruin finals)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.services.edge_lifecycle.capital_cert_bankruptcy import (
    apply_bankruptcy_to_capital_lane_row,
    detect_account_bankruptcy,
)
from src.domain.services.edge_lifecycle.capital_cert_promote import (
    CAPITAL_CERT_STATUS_CERTIFIED,
    cryptobt_capital_cert_passes,
)


def _trade(net_pnl: float) -> SimpleNamespace:
    return SimpleNamespace(net_pnl=net_pnl, exit_type="stop_loss")


class TestDetectAccountBankruptcy:
    def test_solvent_book_is_not_bankrupt(self) -> None:
        trades = [_trade(1_000.0), _trade(-500.0), _trade(2_000.0)]
        out = detect_account_bankruptcy(initial_capital=10_000.0, trades=trades, final_balance=12_500.0)
        assert out.account_bankrupt is False
        assert out.fantasy_post_ruin_trades == 0
        assert out.ruin_trade_index is None

    def test_wiped_final_balance_is_bankrupt(self) -> None:
        trades = [_trade(-4_000.0), _trade(-7_000.0)]
        out = detect_account_bankruptcy(initial_capital=10_000.0, trades=trades, final_balance=0.0)
        assert out.account_bankrupt is True
        assert out.ruin_trade_index == 1
        assert out.fantasy_post_ruin_trades == 0

    def test_trades_after_ruin_are_fantasy(self) -> None:
        """Regression: fixed-notional books that kept trading through ruin."""
        trades = [
            _trade(-6_000.0),
            _trade(-5_000.0),  # cumulative <= 0 here
            _trade(50_000.0),  # fantasy recovery
            _trade(100_000.0),
        ]
        out = detect_account_bankruptcy(
            initial_capital=10_000.0,
            trades=trades,
            final_balance=149_000.0,
        )
        assert out.account_bankrupt is True
        assert out.ruin_trade_index == 1
        assert out.fantasy_post_ruin_trades == 2


class TestApplyBankruptcyToCapitalLaneRow:
    def test_fantasy_final_is_zeroed(self) -> None:
        row = {
            "lane": "perp_5x",
            "initial_capital": 10_000.0,
            "final_capital": 709_520.0,
            "final_balance": 709_520.0,
            "total_return": 69.952,
            "return_pct": 6995.2,
            "net_pnl": 699_520.0,
        }
        trades = [
            _trade(-6_000.0),
            _trade(-5_000.0),
            _trade(350_000.0),
            _trade(360_520.0),
        ]
        out = apply_bankruptcy_to_capital_lane_row(row, trades=trades)
        assert out["account_bankrupt"] is True
        assert out["fantasy_post_ruin_trades"] == 2
        assert out["final_capital"] == 0.0
        assert out["final_balance"] == 0.0
        assert out["total_return"] == pytest.approx(-1.0)
        assert out["return_pct"] == pytest.approx(-100.0)
        assert out["net_pnl"] == pytest.approx(-10_000.0)

    def test_solvent_row_unchanged_except_flag(self) -> None:
        row = {
            "lane": "spot_10k",
            "initial_capital": 10_000.0,
            "final_capital": 29_675.0,
            "final_balance": 29_675.0,
            "total_return": 1.9675,
            "return_pct": 196.75,
            "net_pnl": 19_675.0,
        }
        out = apply_bankruptcy_to_capital_lane_row(row, trades=[_trade(19_675.0)])
        assert out["account_bankrupt"] is False
        assert out["final_capital"] == 29_675.0


class TestPromoteRejectsBankruptLanes:
    def test_bankrupt_perp_3x_fails_even_if_spot_grew(self) -> None:
        modes = {
            "spot_10k": {
                "initial_capital": 10_000.0,
                "final_balance": 15_000.0,
                "final_capital": 15_000.0,
                "account_bankrupt": False,
            },
            "perp_3x": {
                "initial_capital": 10_000.0,
                "final_balance": 0.0,
                "final_capital": 0.0,
                "account_bankrupt": True,
            },
        }
        assert cryptobt_capital_cert_passes({"status": CAPITAL_CERT_STATUS_CERTIFIED, "capital_modes": modes}) is False

    def test_bankrupt_flag_fails_even_when_final_still_positive(self) -> None:
        """Stamped bankrupt (fantasy truncated) must not promote."""
        modes = {
            "spot_10k": {
                "initial_capital": 10_000.0,
                "final_balance": 15_000.0,
                "final_capital": 15_000.0,
                "account_bankrupt": False,
            },
            "perp_3x": {
                "initial_capital": 10_000.0,
                "final_balance": 240_000.0,
                "final_capital": 240_000.0,
                "account_bankrupt": True,
            },
        }
        assert cryptobt_capital_cert_passes({"status": CAPITAL_CERT_STATUS_CERTIFIED, "capital_modes": modes}) is False
