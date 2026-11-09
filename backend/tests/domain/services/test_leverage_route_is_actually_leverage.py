"""The LEVERAGE route must be reached by LEVERAGE, not by a de-risked spot cell.

REUSE-AUDIT: considered `tests/unit/research/test_no_promotion_without_capital_cert.py` and
did NOT extend it — that file judges REGISTRY ROWS (does a promoted row carry a cert at all).
This one judges the PREDICATE `_leverage_route_passes`. Different subject, different SRP.

MEASURED 2026-08-28, re-evaluating `cryptobt_capital_cert_passes` over every cert on disk whose
`capital_modes` carries a `promote_gate` (16 artifacts):

    stored promote_gate != recomputed : 4   (stale values a reader would promote on)
    sized-spot cells present          : 12 of 16

`build_strategy_sleeve_capital_cert` keys its cells `lane_size` — `spot_10k`, `spot_10k_2pct`,
`spot_10k_10pct`, `perp_3x`, `perp_3x_2pct`, ... `_leverage_route_passes` skips only the key that
equals `_SPOT_LANE` exactly, so EVERY REDUCED-SIZING SPOT CELL is iterated as though it were a
leverage lane.

Measured on `execsim_BTC_USDT_4h.json`: all-in spot ends at $8,973 — below its $10,000 start, so
the spot route correctly fails — and then `spot_10k_2pct` at $9,978 clears the $9,830 buy-and-hold
and passes through the LEVERAGE route. A 2%-sized SPOT book was certified as "money at leverage".

Why that is the wrong answer and not a technicality: the leverage route exists to grant exactly one
claim from `ml-gate-leverage-capital-cert.md` — "marginal or even negative on SPOT but compounding
profitably at leverage without liquidating IS a valid, promotable ML signal". Taking LESS spot
exposure is the opposite of that claim. It is the same book, de-risked, losing less.

The fix keys on the row's own `leverage` value rather than on the spelling of its dict key, so it
holds for any future key scheme.
"""

from __future__ import annotations

from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_promote import cryptobt_capital_cert_passes


def _cell(
    *,
    leverage: float,
    final: float,
    initial: float = 10_000.0,
    liquidations: int = 0,
    bankrupt: bool = False,
) -> dict[str, Any]:
    return {
        "leverage": leverage,
        "initial_capital": initial,
        "final_capital": final,
        "final_balance": final,
        "liquidation_exits": liquidations,
        "account_bankrupt": bankrupt,
    }


def _cert(modes: dict[str, Any], *, bh: float) -> dict[str, Any]:
    """A cert shaped so ONLY the leverage route is under test.

    `window_is_in_sample` False and a present `headline_deflated_sharpe` are required by earlier
    guards in the predicate; without them it refuses before reaching the route being measured.
    """
    return {
        "capital_modes": modes,
        "spot_bh_final": bh,
        "window_is_in_sample": False,
        "headline_deflated_sharpe": 0.5,
    }


class TestASizedSpotCellIsNotALeverageLane:
    def test_a_reduced_sizing_spot_cell_does_not_pass_the_leverage_route(self) -> None:
        """The measured execsim_BTC_USDT_4h shape: all-in spot loses, 2% spot 'wins'."""
        cert = _cert(
            {
                "spot_10k": _cell(leverage=1.0, final=8_973.0),
                "spot_10k_2pct": _cell(leverage=1.0, final=9_978.0),
            },
            bh=9_830.0,
        )
        assert cryptobt_capital_cert_passes(cert) is False

    def test_every_spot_sizing_losing_money_still_fails(self) -> None:
        cert = _cert(
            {
                "spot_10k": _cell(leverage=1.0, final=8_973.0),
                "spot_10k_2pct": _cell(leverage=1.0, final=9_978.0),
                "spot_10k_10pct": _cell(leverage=1.0, final=9_900.0),
                "spot_10k_50pct": _cell(leverage=1.0, final=9_400.0),
            },
            bh=9_830.0,
        )
        assert cryptobt_capital_cert_passes(cert) is False


class TestALosingLaneIsNotAMoneyMaker:
    """ "Beat a falling benchmark" is not the same as "made money", and only one of them promotes.

    MEASURED 2026-08-28 over every cert on disk: exactly 5 pass the predicate today, and all 5
    would flip under this requirement — so it costs the corpus NOTHING and closes a real hole.

    The asymmetry it removes: the SPOT route already demands `capital_backtest_passes`, i.e.
    absolute growth, AND beating B&H. The leverage route demanded only the latter, so a levered
    lane ending BELOW its own starting capital promoted whenever BTC fell further. Measured on
    `execsim_BTC_USDT_4h.json`: `perp_3x_2pct` ends at $9,935 of $10,000 and clears a $9,830
    buy-and-hold.

    `ml-gate-leverage-capital-cert.md` grants the leverage route to a book "COMPOUNDING PROFITABLY
    at leverage without liquidating". A lane at $9,935 on $10,000 has not compounded profitably,
    and a user holding CASH beat it. The gate was more permissive than the rule it implements.
    """

    def test_a_levered_lane_above_bh_but_below_its_own_start_does_not_pass(self) -> None:
        cert = _cert(
            {
                "spot_10k": _cell(leverage=1.0, final=8_973.0),
                "perp_3x_2pct": _cell(leverage=3.0, final=9_935.0),
            },
            bh=9_830.0,
        )
        assert cryptobt_capital_cert_passes(cert) is False

    def test_a_levered_lane_that_makes_money_and_beats_bh_still_passes(self) -> None:
        cert = _cert(
            {
                "spot_10k": _cell(leverage=1.0, final=8_973.0),
                "perp_3x_2pct": _cell(leverage=3.0, final=10_400.0),
            },
            bh=9_830.0,
        )
        assert cryptobt_capital_cert_passes(cert) is True


class TestRealLeverageStillPasses:
    """The route must keep granting what the ml-gate rule exists to grant."""

    def test_a_surviving_perp_lane_above_bh_passes_though_spot_lost(self) -> None:
        cert = _cert(
            {
                "spot_10k": _cell(leverage=1.0, final=8_973.0),
                "perp_5x": _cell(leverage=5.0, final=16_165.0),
            },
            bh=9_830.0,
        )
        assert cryptobt_capital_cert_passes(cert) is True

    def test_a_sized_perp_lane_counts_too(self) -> None:
        """Sizing is a lever ON a leverage lane; only leverage == 1 is disqualified."""
        cert = _cert(
            {
                "spot_10k": _cell(leverage=1.0, final=8_973.0),
                "perp_5x_10pct": _cell(leverage=5.0, final=12_400.0),
            },
            bh=9_830.0,
        )
        assert cryptobt_capital_cert_passes(cert) is True

    def test_a_liquidating_perp_lane_does_not_pass(self) -> None:
        cert = _cert(
            {
                "spot_10k": _cell(leverage=1.0, final=8_973.0),
                "perp_8x": _cell(leverage=8.0, final=20_000.0, liquidations=2),
            },
            bh=9_830.0,
        )
        assert cryptobt_capital_cert_passes(cert) is False

    def test_a_lane_missing_its_leverage_field_is_judged_by_its_key(self) -> None:
        """Older certs predate the `leverage` field; the spot PREFIX still disqualifies them."""
        row = _cell(leverage=1.0, final=9_978.0)
        del row["leverage"]
        cert = _cert({"spot_10k": _cell(leverage=1.0, final=8_973.0), "spot_10k_2pct": row}, bh=9_830.0)
        assert cryptobt_capital_cert_passes(cert) is False
