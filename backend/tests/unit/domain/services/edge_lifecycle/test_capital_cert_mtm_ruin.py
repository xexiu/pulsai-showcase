"""A -100% mark-to-market drawdown IS ruin, even when closed trades never sum below zero.

MEASURED 2026-08-17 across 518 cert artifacts / 463,946 capital-shaped cells: **892 cells**
report a drawdown meaning "equity touched zero" while ALSO reporting a final above initial,
`account_bankrupt: False`, and zero fantasy trades. Real example, published at 3.69x B&H in
the money ledger:

    models/btc_usdt_1d/lightgbm/v42/capital_certification.json
      capital_modes.perp_8x
      max_drawdown = -1.0   final_capital = 16004.32   initial = 10000.00
      liquidation_exits = 0   account_bankrupt = False   fantasy_post_ruin_trades = 0

Both numbers cannot be true. `detect_account_bankruptcy` walks REALIZED trade net_pnl only,
so an account wiped intrabar — which is precisely what the honest MTM drawdown measures —
never trips it. That is the same closed-trade blindness `mark_to_market_max_drawdown` was
introduced to remove, surviving one layer up in the packer.
"""

from __future__ import annotations

from src.domain.services.edge_lifecycle.capital_cert_bankruptcy import (
    apply_bankruptcy_to_capital_lane_row,
    detect_account_bankruptcy,
)


class _Trade:
    """Minimal trade stub — the packer reads only net_pnl."""

    def __init__(self, net_pnl: float) -> None:
        self.net_pnl = net_pnl


class TestMarkToMarketWipeIsRuin:
    def test_full_mtm_drawdown_is_ruin_even_when_closed_trades_are_profitable(self) -> None:
        """The v42 perp_8x shape: every closed trade green, equity path hit zero."""
        detection = detect_account_bankruptcy(
            initial_capital=10_000.0,
            trades=[_Trade(3_000.0), _Trade(3_004.32)],
            final_balance=16_004.32,
            mark_to_market_drawdown=-1.0,
        )
        assert detection.account_bankrupt is True

    def test_a_survivable_drawdown_is_not_ruin(self) -> None:
        detection = detect_account_bankruptcy(
            initial_capital=10_000.0,
            trades=[_Trade(3_000.0)],
            final_balance=13_000.0,
            mark_to_market_drawdown=-0.384,
        )
        assert detection.account_bankrupt is False

    def test_percent_scaled_drawdown_is_understood(self) -> None:
        """Artifacts store -1.0 and -100.0 for the same thing; both mean wiped."""
        detection = detect_account_bankruptcy(
            initial_capital=10_000.0,
            trades=[_Trade(6_004.32)],
            final_balance=16_004.32,
            mark_to_market_drawdown=-100.0,
        )
        assert detection.account_bankrupt is True

    def test_absent_drawdown_keeps_the_old_behaviour(self) -> None:
        """Callers that pass no drawdown must be unaffected."""
        detection = detect_account_bankruptcy(
            initial_capital=10_000.0,
            trades=[_Trade(6_004.32)],
            final_balance=16_004.32,
        )
        assert detection.account_bankrupt is False


class TestTheRowIsFlooredNotLeftContradictory:
    def test_the_measured_v42_row_is_floored_to_ruin(self) -> None:
        row = {
            "lane": "perp_8x",
            "initial_capital": 10_000.0,
            "final_capital": 16_004.32,
            "max_drawdown": -1.0,
            "liquidation_exits": 0,
        }
        out = apply_bankruptcy_to_capital_lane_row(row, trades=[_Trade(6_004.32)])
        assert out["account_bankrupt"] is True
        assert out["final_capital"] == 0.0
        assert out["total_return"] == -1.0
        assert out["return_pct"] == -100.0

    def test_a_healthy_row_is_untouched(self) -> None:
        row = {
            "lane": "perp_5x",
            "initial_capital": 10_000.0,
            "final_capital": 12_299.0,
            "max_drawdown": -0.392,
            "liquidation_exits": 0,
        }
        out = apply_bankruptcy_to_capital_lane_row(row, trades=[_Trade(2_299.0)])
        assert out["account_bankrupt"] is False
        assert out["final_capital"] == 12_299.0

    def test_no_drawdown_key_still_packs(self) -> None:
        row = {"initial_capital": 10_000.0, "final_capital": 11_000.0}
        out = apply_bankruptcy_to_capital_lane_row(row, trades=[_Trade(1_000.0)])
        assert out["account_bankrupt"] is False
        assert out["final_capital"] == 11_000.0
