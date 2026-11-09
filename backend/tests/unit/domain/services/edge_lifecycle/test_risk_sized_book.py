"""The risk-sized money grade (P1-0): each trade risks a fixed fraction of CURRENT equity, isolated margin per lane.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.

The owner's own case, 2026-10-04: "$20 capital, only $2 risk, 50x, thin SL, TP ladder, BE after TP2 -- ALL-IN is
another case". So the numbers below are a $20 account risking 10% a trade; the expected values are worked by hand
from the rule (notional = risk / stop distance, capped at leverage x equity; a liquidation loses only the margin).
"""

from __future__ import annotations

import pytest

from src.domain.services.edge_lifecycle.capital_cert_headline import EXCLUDED_LIQUIDATED
from src.domain.services.edge_lifecycle.risk_sized_book import (
    RiskSizedLane,
    RiskTrade,
    certify_risk_sized_lanes,
    risk_sized_notional,
    simulate_risk_sized_lane,
)
from src.shared.constants.capital_cert_harness import CAPITAL_CERT_HARNESS_RISK_SIZED_BOOK

OWNER_CAPITAL = 20.0
OWNER_RISK = 0.10  # $2 of $20


def _lane(trades: list[RiskTrade], leverage: float, risk: float = OWNER_RISK) -> RiskSizedLane:
    return simulate_risk_sized_lane(trades, initial_capital=OWNER_CAPITAL, leverage=leverage, risk_fraction=risk)


def test_a_stop_out_loses_exactly_the_risk() -> None:
    # 1% stop -> $200 notional for $2 at risk; 50x needs only $4 margin; the stop fills -> -$2.
    out = _lane([RiskTrade(side=1, stop_frac=0.01, net_return=-0.01, worst_adverse=0.01)], 50)
    assert out["final_capital"] == pytest.approx(18.0)
    assert out["liquidation_exits"] == 0


def test_the_risk_is_a_fraction_of_current_equity_so_wins_compound() -> None:
    # +2R on $20 -> $24; the next trade risks 10% of $24 = $2.40, not the original $2.
    trades = [
        RiskTrade(side=1, stop_frac=0.01, net_return=0.02, worst_adverse=0.003),
        RiskTrade(side=-1, stop_frac=0.01, net_return=-0.01, worst_adverse=0.01),
    ]
    out = _lane(trades, 50)
    assert out["final_capital"] == pytest.approx(21.6)
    assert out["num_trades"] == 2


def test_the_lane_can_record_its_equity_after_every_trade() -> None:
    """SOL-V2-CHART (2026-10-14): a chart's equity line is the grade's own walk, trade by trade -- a skipped spot short
    keeps the equity it found, and the path ends at the lane's final capital."""
    trades = [
        RiskTrade(side=1, stop_frac=0.01, net_return=0.02, worst_adverse=0.003),
        RiskTrade(side=-1, stop_frac=0.01, net_return=-0.01, worst_adverse=0.01),
    ]
    path: list[float] = []
    out = simulate_risk_sized_lane(trades, initial_capital=OWNER_CAPITAL, leverage=50, risk_fraction=OWNER_RISK, equity_after=path)
    assert path == pytest.approx([24.0, 21.6])
    assert path[-1] == pytest.approx(out["final_capital"])
    spot: list[float] = []
    simulate_risk_sized_lane(trades, initial_capital=OWNER_CAPITAL, leverage=1, risk_fraction=OWNER_RISK, equity_after=spot)
    assert len(spot) == 2
    assert spot[1] == spot[0]  # the short is skipped on spot: the equity it found, carried


def test_the_lane_caps_notional_at_leverage_times_equity() -> None:
    # A 0.1% stop wants $2,000 of notional; 50x allows $1,000, so the stop-out costs $1, not $2.
    out = _lane([RiskTrade(side=1, stop_frac=0.001, net_return=-0.001, worst_adverse=0.001)], 50)
    assert out["final_capital"] == pytest.approx(19.0)


def test_a_gap_past_liquidation_loses_only_the_margin() -> None:
    # 50x liquidates 1/50 - 0.4% maintenance = 1.6% away; a 5% gap through the 1% stop costs the $4 margin, not $10.
    out = _lane([RiskTrade(side=1, stop_frac=0.01, net_return=-0.05, worst_adverse=0.05)], 50)
    assert out["final_capital"] == pytest.approx(16.0)
    assert out["liquidation_exits"] == 1
    assert out["account_liquidated"] is True


def test_a_stop_set_beyond_liquidation_is_liquidated_on_the_way_there() -> None:
    # A 3% stop at 50x: price reaches the 1.6% liquidation first -> the margin ($66.67 / 50 = $1.33) is gone.
    out = _lane([RiskTrade(side=1, stop_frac=0.03, net_return=-0.03, worst_adverse=0.02)], 50)
    assert out["final_capital"] == pytest.approx(OWNER_CAPITAL - (2.0 / 0.03) / 50)
    assert out["liquidation_exits"] == 1


def test_spot_never_shorts_never_liquidates_and_never_exceeds_the_account() -> None:
    trades = [
        RiskTrade(side=-1, stop_frac=0.01, net_return=0.05, worst_adverse=0.0),
        RiskTrade(side=1, stop_frac=0.01, net_return=-0.01, worst_adverse=0.01),
        RiskTrade(side=1, stop_frac=0.01, net_return=-0.5, worst_adverse=0.5),
    ]
    out = _lane(trades, 1)
    # The short is skipped; each long is capped at the $ in the account (1x): -0.2 then -0.5 x $19.80.
    assert out["n_skipped_shorts"] == 1
    assert out["liquidation_exits"] == 0
    assert out["final_capital"] == pytest.approx(19.8 - 0.5 * 19.8)


def test_the_drawdown_is_marked_at_the_worst_adverse_point_not_at_the_exit() -> None:
    # The trade ends +2R, but while open it was 0.8% against a $200 position: $20 -> $18.40 is an 8% drawdown.
    out = _lane([RiskTrade(side=1, stop_frac=0.01, net_return=0.02, worst_adverse=0.008)], 50)
    assert out["final_capital"] == pytest.approx(24.0)
    assert out["max_drawdown_pct"] == pytest.approx(-8.0)


def test_a_lost_account_stops_trading() -> None:
    # Risking everything at 3x: the liquidation takes the whole $20 margin; the next trade never happens.
    trades = [
        RiskTrade(side=1, stop_frac=0.01, net_return=-0.5, worst_adverse=0.5),
        RiskTrade(side=1, stop_frac=0.01, net_return=0.5, worst_adverse=0.0),
    ]
    out = _lane(trades, 3, risk=1.0)
    assert out["final_capital"] == pytest.approx(0.0)
    assert out["account_bankrupt"] is True
    assert out["trades_after_ruin_skipped"] == 1


def test_bad_inputs_are_refused_not_graded() -> None:
    with pytest.raises(ValueError, match="risk_fraction"):
        _lane([], 3, risk=0.0)
    with pytest.raises(ValueError, match="stop_frac"):
        _lane([RiskTrade(side=1, stop_frac=0.0, net_return=0.0, worst_adverse=0.0)], 3)


def test_the_ladder_grades_every_lane_and_names_the_ones_that_liquidated() -> None:
    # A 5% stop that was 20% against at its worst: 8x liquidates 12.1% away, 3x (32.9%) and spot survive.
    trades = [RiskTrade(side=1, stop_frac=0.05, net_return=-0.06, worst_adverse=0.2)]
    cert = certify_risk_sized_lanes(trades, initial_capital=OWNER_CAPITAL, leverages=(1, 3, 8), risk_fraction=OWNER_RISK)
    assert cert["harness"] == CAPITAL_CERT_HARNESS_RISK_SIZED_BOOK
    assert list(cert["lanes"]) == ["spot_10k", "perp_3x", "perp_8x"]
    assert cert["liquidated_lanes"] == ["perp_8x"]
    assert cert["lanes"]["perp_8x"].get("ruin_reason") == EXCLUDED_LIQUIDATED
    assert cert["max_clean_leverage_survived"] == 3
    assert cert["risk_fraction"] == OWNER_RISK


@pytest.mark.parametrize(
    ("stop_frac", "leverage", "expected"),
    [
        (0.01, 20.0, 10_000.0),  # 10 % of $1,000 lost at a 1 % stop -> $10,000 of notional
        (0.002, 20.0, 20_000.0),  # the same risk at a 0.2 % stop would be $50,000: capped at 20 x the equity
        (0.01, 1.0, 1_000.0),  # spot: never more than the equity
    ],
)
def test_the_one_sizing_rule_risks_the_fraction_at_the_stop_capped_by_the_lane(stop_frac: float, leverage: float, expected: float) -> None:
    """BACKTEST-ONE S2b: the rule the grade walks and the engine sizes with -- one definition, called by both."""
    assert risk_sized_notional(1_000.0, stop_frac, leverage=leverage, risk_fraction=0.10) == pytest.approx(expected)
