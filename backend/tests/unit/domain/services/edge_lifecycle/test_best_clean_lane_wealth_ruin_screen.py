"""`best_clean_lane_wealth` must apply the SAME ruin screen as everything else.

THE DEFECT (2026-08-12, third site). This function screened `liquidation_exits` and
`account_bankrupt` and NOT the mark-to-market wipe. So `1d lightgbm v42`'s `perp_7x` cell —

    final $24,235 · 4.03x B&H · 152 trades · liquidation_exits 0 · account_bankrupt False
    max_drawdown -98.9%   ->  headline_exclusion_reason = mtm_drawdown_wipe

— passed it, and the money ledger printed it as the corpus's TOP performer on unseen data. A cell
that took the account to ~zero was ranked first among B&H beaters.

WHY THE DOCSTRING'S ARGUMENT DOES NOT COVER THIS. The function deliberately DISCLOSES drawdown
rather than screening it, and that reasoning is sound: an arbitrary floor (a -0.40 cap was tried
and reverted) would have deleted `1d gb v10`, the corpus's only pre-commitment survivor at the
time, which carries -69%. But -98.9% is not a deep drawdown to be disclosed — it is the account
GONE, which is why `headline_exclusion_reason` classes it with liquidation and bankruptcy.
Screening RUIN and screening RISK APPETITE are different things, and only the first belongs here.

This is the same "two screens, one question" defect fixed earlier the same day between
`precommit_tier` and `headline_exclusion_reason` (b5f6d40e1). Third site, same cause: a copy of
the rule that drifted from the SoT.
"""

from __future__ import annotations

from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_promote import best_clean_lane_wealth


def _cert(**lanes: dict[str, Any]) -> dict[str, Any]:
    return {
        "spot_bh_final": 6_020.0,
        "capital_modes": {},
        "capital_x_exit": {"best_by_capital_lane": {lane: {"best": cell, "n_valid": 3} for lane, cell in lanes.items()}},
    }


def _cell(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "final_capital": 20_000.0,
        "initial_capital": 10_000.0,
        "liquidation_exits": 0,
        "account_bankrupt": False,
        "max_drawdown": -0.30,
        "num_trades": 150,
    }
    base.update(over)
    return base


class TestTheMtmWipeIsRuin:
    def test_a_wiped_lane_is_not_the_richest_clean_lane(self) -> None:
        """v42's exact shape: richest lane, zero liquidations, and -98.9% drawdown."""
        cert = _cert(
            perp_3x=_cell(final_capital=16_101.0, max_drawdown=-0.466),
            perp_7x=_cell(final_capital=24_235.0, max_drawdown=-0.989),
        )

        best = best_clean_lane_wealth(cert)

        assert best is not None
        assert best["lane"] == "perp_3x"
        assert best["final_capital"] == 16_101.0

    def test_a_fully_wiped_lane_is_excluded(self) -> None:
        cert = _cert(perp_8x=_cell(final_capital=99_000.0, max_drawdown=-1.0))

        assert best_clean_lane_wealth(cert) is None

    def test_liquidation_is_still_screened(self) -> None:
        cert = _cert(perp_5x=_cell(final_capital=99_000.0, liquidation_exits=2))

        assert best_clean_lane_wealth(cert) is None

    def test_bankruptcy_is_still_screened(self) -> None:
        cert = _cert(perp_5x=_cell(final_capital=99_000.0, account_bankrupt=True))

        assert best_clean_lane_wealth(cert) is None


class TestDeepDrawdownIsSTILLDisclosedNotScreened:
    """The reverted -0.40 floor must not sneak back in under cover of the wipe screen."""

    def test_a_minus_69_percent_lane_still_wins(self) -> None:
        """`1d gb v10` carries -69% and is a real book — screening it was the earlier mistake."""
        cert = _cert(
            spot_10k=_cell(final_capital=11_000.0, max_drawdown=-0.05),
            perp_5x=_cell(final_capital=17_774.0, max_drawdown=-0.69),
        )

        best = best_clean_lane_wealth(cert)

        assert best is not None
        assert best["lane"] == "perp_5x"
        assert best["max_drawdown"] == -0.69

    def test_a_minus_86_percent_lane_still_wins(self) -> None:
        """v42's perp_6x: -86.7%, zero liquidations. Deep, disclosed, NOT ruin."""
        cert = _cert(
            perp_3x=_cell(final_capital=16_101.0, max_drawdown=-0.466),
            perp_6x=_cell(final_capital=22_202.0, max_drawdown=-0.867),
        )

        best = best_clean_lane_wealth(cert)

        assert best is not None
        assert best["lane"] == "perp_6x"
