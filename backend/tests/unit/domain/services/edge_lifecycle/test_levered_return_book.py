"""A continuous return book must be turned into capital the same way everywhere.

WHY THIS EXISTS (2026-08-09). `standing_vrp_always` is the registry's only `edge`, is
`production_promoted`, is charted to users — and `cert_registry_leaves_capital.py` returns
`inapplicable_vrp_venue` for it. CryptoBacktester simulates discrete BTC spot/perp trades;
a short-variance book has no entries and exits to simulate, so its money outcome was not
merely unmeasured, it was unmeasurable with what existed.

It is not unmeasurable in principle. The VRP book already produces a per-bar net return
series (`vol_risk_premium_validate.build()` -> iv^2 - rv^2, scaled), and 3,871 daily DVOL
points are on disk. What was missing is the primitive that turns ANY continuous return
series into a capital curve with leverage lanes, an honest mark-to-market drawdown and ruin
detection.

`funding_ml_carry_portfolio_backtest` has that logic, but buried inside a coin-legs loop
over `weights_json` / `fund_gross` / `price_gross`, so a single-series book cannot reach it.
This is the extraction that harness never did — not a fork of it.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.domain.services.edge_lifecycle.levered_return_book import (
    simulate_levered_return_book,
)


def _flat(n: int, r: float) -> pd.Series:
    return pd.Series([r] * n, index=pd.date_range("2021-01-01", periods=n, freq="D"))


def test_unlevered_compounding_matches_the_closed_form() -> None:
    # Capital is reported in CENTS (money, not a float toy), so compare to the cent.
    out = simulate_levered_return_book(_flat(10, 0.01), initial_capital=10_000.0, leverage=1)
    assert out["final_capital"] == pytest.approx(10_000.0 * (1.01**10), abs=0.01)
    assert out["account_liquidated"] is False
    assert out["max_drawdown_pct"] == pytest.approx(0.0)


def test_leverage_multiplies_the_per_bar_return_not_the_final_result() -> None:
    """3x on +1% per bar compounds at 1.03 per bar — NOT 3x the unlevered total.

    Getting this wrong is how a levered headline becomes fantasy: scaling the final number
    instead of the path hides every drawdown the path went through.
    """
    out = simulate_levered_return_book(_flat(10, 0.01), initial_capital=10_000.0, leverage=3)
    assert out["final_capital"] == pytest.approx(10_000.0 * (1.03**10), abs=0.01)


def test_drawdown_is_marked_every_bar_not_only_at_the_end() -> None:
    """Down 30% then back up: final is near flat, but the DD must still record the pit."""
    rets = pd.Series(
        [-0.30, 0.30 / 0.70],  # -30% then exactly back to par
        index=pd.date_range("2021-01-01", periods=2, freq="D"),
    )
    out = simulate_levered_return_book(rets, initial_capital=10_000.0, leverage=1)
    assert out["final_capital"] == pytest.approx(10_000.0, abs=0.01)
    assert out["max_drawdown_pct"] == pytest.approx(-30.0, abs=1e-6)


def test_a_lane_that_wipes_the_account_is_liquidated_not_negative() -> None:
    """-40% at 3x is -120%: capital floors at 0 and the lane is marked liquidated.

    The corpus rule is explicit that a book which liquidates the user is not a money-maker,
    so the lane has to SAY it rather than report a negative balance.
    """
    rets = pd.Series([-0.40, 0.50], index=pd.date_range("2021-01-01", periods=2, freq="D"))
    out = simulate_levered_return_book(rets, initial_capital=10_000.0, leverage=3)
    assert out["final_capital"] == 0.0
    assert out["account_liquidated"] is True
    assert out["max_drawdown_pct"] == pytest.approx(-100.0)


def test_no_trading_after_ruin() -> None:
    """A recovery bar after wipeout must not resurrect the account (fantasy_post_ruin)."""
    rets = pd.Series([-1.0, 5.0], index=pd.date_range("2021-01-01", periods=2, freq="D"))
    out = simulate_levered_return_book(rets, initial_capital=10_000.0, leverage=1)
    assert out["final_capital"] == 0.0
    assert out["account_liquidated"] is True
    assert out["bars_after_ruin_skipped"] == 1


def test_per_bar_cost_is_charged_on_the_levered_notional() -> None:
    out = simulate_levered_return_book(_flat(1, 0.0), initial_capital=10_000.0, leverage=4, cost_per_bar=0.001)
    assert out["final_capital"] == pytest.approx(10_000.0 * (1 - 4 * 0.001), abs=0.01)


def test_empty_series_returns_the_initial_capital_untouched() -> None:
    out = simulate_levered_return_book(pd.Series(dtype=float), initial_capital=10_000.0, leverage=5)
    assert out["final_capital"] == 10_000.0
    assert out["n_bars"] == 0
    assert out["account_liquidated"] is False


def test_non_finite_returns_are_refused_rather_than_silently_compounded() -> None:
    """A NaN bar must not quietly become a 0% bar — that is how a gap flatters a book."""
    rets = pd.Series([0.01, math.nan], index=pd.date_range("2021-01-01", periods=2, freq="D"))
    with pytest.raises(ValueError, match="non-finite"):
        simulate_levered_return_book(rets, initial_capital=10_000.0, leverage=1)


class TestRuinIsTerminalNotJustExactZero:
    """Reaching the ruin line ends the account; it cannot compound back from a sliver.

    MEASURED 2026-08-20 on `hunt_vt17_short_mom_ic_4h.json` (confirm/OOS 2019-01-01..2026-08-01,
    16,610 bars, 15 folds, spot B&H $170,599, the runner's own cell — no re-selection): the
    `perp_3x` lane reports **$60,995,315 from $10,000 beside a -99.92% drawdown**, and `perp_4x`
    reports $24,040 beside -100.00%. One leverage notch swings the same book by 2,500x.

    IT IS NOT A MATH ERROR. Under constant-leverage rebalancing `capital *= (1 + L*r)` only reaches
    zero when a SINGLE bar has `L*r <= -1`, so a sequence of merely-terrible bars drives equity to a
    tiny positive fraction and multiplicative compounding then runs from there for thousands of
    bars. The arithmetic is self-consistent. The PRODUCT is not: it assumes infinitely divisible
    capital, no minimum order size, and an account holding $0.004 trading its way back to $61M.

    WHY THIS THRESHOLD AND NOT A PICKED ONE. The venue minimum notional is the physically correct
    floor, but it is reported per-symbol by the exchange (`order_preflight.enforce_min_notional`
    reads `limits.min_notional`) and is simply not available to an offline return-book simulation.
    The one in-repo definition of "the account is gone" is `DRAWDOWN_WIPE_THRESHOLD` in
    `capital_cert_headline`, already used by `headline_exclusion_reason` to screen ruin. Using the
    SAME line to SIMULATE ruin as to JUDGE it means ruin means one thing in both places, instead of
    an engine that manufactures numbers its own screen then throws away.
    """

    def test_a_book_that_reaches_the_ruin_line_cannot_rally_back(self) -> None:
        """The $61M case in miniature: catastrophic decay, then a long violent recovery."""
        crash = [-0.32] * 12  # 3x -> ~-96% cumulative, no single bar wipes (0.32*3 < 1)
        rally = [0.5] * 60
        book = simulate_levered_return_book(pd.Series(crash + rally, dtype=float), initial_capital=10_000.0, leverage=3.0)

        assert book["account_liquidated"] is True, "the account passed the ruin line and kept trading"
        assert book["final_capital"] == 0.0
        # One bar is enough: 1 + 3*(-0.32) = 0.04, a 96% drop, past the wipe line immediately.
        # So the remaining crash bars are skipped alongside the rally, not just the rally.
        assert book["bars_after_ruin_skipped"] == len(crash) - 1 + len(rally)

    def test_a_survivable_drawdown_is_untouched(self) -> None:
        """The over-correction check: -50% is a disclosure, not ruin, and must still recover."""
        book = simulate_levered_return_book(pd.Series([-0.25, -0.05, 0.6, 0.3], dtype=float), initial_capital=10_000.0, leverage=2.0)

        assert book["account_liquidated"] is False
        assert book["final_capital"] > 10_000.0

    def test_a_single_bar_wipe_still_liquidates_as_before(self) -> None:
        """The pre-existing terminal condition must keep working."""
        book = simulate_levered_return_book(pd.Series([-0.40] + [0.5] * 10, dtype=float), initial_capital=10_000.0, leverage=3.0)

        assert book["account_liquidated"] is True
        assert book["final_capital"] == 0.0

    def test_spot_is_held_to_the_same_line(self) -> None:
        """Ruin is ruin: an unlevered book that loses 95% is gone too, not a recovery story."""
        book = simulate_levered_return_book(pd.Series([-0.6] * 4 + [1.0] * 40, dtype=float), initial_capital=10_000.0, leverage=1.0)

        assert book["account_liquidated"] is True
