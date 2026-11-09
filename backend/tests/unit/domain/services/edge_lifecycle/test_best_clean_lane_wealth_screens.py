"""What `best_clean_lane_wealth` screens, and what it must only disclose.

Both behaviours below were WRONG in production on 2026-08-10 and were fixed the same day.
Neither had a test, which is why the second defect was introduced by the fix for the first.

1. A -0.40 drawdown floor was added here on a constant copied from a research helper. The SoT
   filter the rest of the stack uses (`capital_cert_headline.headline_exclusion_reason`)
   disqualifies on RUIN and passes deep drawdowns untouched. The floor contradicted it and
   deleted `1d gb v10` -- the only book in the corpus that survives pre-commitment (+23%,
   $12,298 from $10,000, 2.24x B&H, ZERO liquidations, -69% DD) -- from the money ledger.

2. `8h lightgbm v150` turned $10,000 into $9,457 and still ranked as a candidate on 1.67x
   "beats B&H", because buy-and-hold lost more. Beating a falling benchmark is not making money.

These are BEHAVIOUR tests: each asserts a business outcome (is this book citable, and is its
risk visible), not that a formula runs.
"""

from __future__ import annotations

from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_promote import best_clean_lane_wealth


def _cert(**lane: Any) -> dict[str, Any]:
    """A cert with one lane, shaped like the real `capital_x_exit` artifact."""
    return {
        "window": {"spot_bh_final": 6946.88, "window_is_in_sample": False},
        "capital_x_exit": {
            "best_by_capital_lane": {
                "perp_5x": {
                    "best": {
                        "initial_capital": 10000.0,
                        "sizing": "10pct",
                        "num_trades": 187,
                        **lane,
                    }
                }
            }
        },
    }


class TestRuinIsScreened:
    def test_a_liquidated_lane_is_never_citable(self) -> None:
        """Ruin disqualifies however good the final capital looks.

        `1d gb v12` finished +25% WITH four liquidations. Fixed per-trade sizing means each
        liquidation burns only that position's margin, so the account survives and the headline
        reads as profit -- while the user was wiped out four times.
        """
        result = best_clean_lane_wealth(_cert(final_capital=12497.89, max_drawdown=-1.0, liquidation_exits=4))
        assert result is None, "a book that liquidated the user is not a money-maker"

    def test_a_bankrupt_account_is_never_citable(self) -> None:
        result = best_clean_lane_wealth(_cert(final_capital=12497.89, max_drawdown=-1.0, account_bankrupt=True))
        assert result is None


class TestDrawdownIsDisclosedNotScreened:
    def test_a_deep_drawdown_book_stays_citable(self) -> None:
        """REGRESSION for the -0.40 floor I added and removed the same day.

        v10's real numbers. If a future change reintroduces an absolute DD cap here, this fails
        and names what it costs: the corpus's only pre-commitment survivor.
        """
        result = best_clean_lane_wealth(_cert(final_capital=17131.67, max_drawdown=-0.723, liquidation_exits=0))
        assert result is not None, "a -72% drawdown is a risk to disclose, not grounds to exclude"
        assert result["beats_bh_wealth"] is True

    def test_the_drawdown_is_reported_to_the_caller(self) -> None:
        """Computing a value and never surfacing it has shipped twice here already."""
        result = best_clean_lane_wealth(_cert(final_capital=17131.67, max_drawdown=-0.723, liquidation_exits=0))
        assert result is not None
        assert result["max_drawdown"] == -0.723, "risk must reach the reader, not vanish in a filter"

    def test_a_percentage_drawdown_is_normalised_to_a_fraction(self) -> None:
        """Writers disagree: some store -72.3, some -0.723. A reader must not see a 72x error."""
        result = best_clean_lane_wealth(_cert(final_capital=17131.67, max_drawdown_pct=-72.3, liquidation_exits=0))
        assert result is not None
        assert result["max_drawdown"] == -0.723


class TestAbsoluteLossIsScreened:
    def test_losing_money_is_not_a_win_even_when_it_beats_bh(self) -> None:
        """`8h v150`: $10,000 -> $9,457 while B&H fell further. 1.67x on a shrinking account."""
        result = best_clean_lane_wealth(_cert(final_capital=9457.0, max_drawdown=-0.227, liquidation_exits=0))
        assert result is None, "the objective is making money, not losing less than BTC did"

    def test_a_profitable_book_that_beats_bh_is_citable(self) -> None:
        result = best_clean_lane_wealth(_cert(final_capital=19958.63, max_drawdown=-0.295, liquidation_exits=0))
        assert result is not None
        assert result["final_capital"] == 19958.63
        assert result["beats_bh_wealth"] is True
