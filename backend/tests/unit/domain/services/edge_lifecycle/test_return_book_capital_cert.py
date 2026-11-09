"""Behaviour: a continuous return book gets a leverage cert with liquidation MEASURED.

Measured 2026-08-19 across the hunt corpus: 397 of 397 cells asserting a leveraged beats-B&H
claim carry `liquidation_exits: null`. The hypothesis route never reaches the cross-product
engine (`run_edge_capital_x_exit_grid.py` keys on a persisted ModelSpec directory, which a
hunt cell never writes), so survivability was simply never computed for any of them.

`ml-gate-leverage-capital-cert.md` forbids concluding KILL/NULL from a spot-only gate, which
makes every one of those verdicts incomplete rather than wrong.

REUSE-AUDIT: `simulate_levered_return_book` already compounds a per-bar series at leverage with
honest per-bar drawdown and TERMINAL ruin — it is the primitive, and this crosses it over the
lanes rather than reimplementing the maths. Considered
`run_edge_capital_x_exit_grid.py` (ModelSpec-keyed, cannot take an in-memory series) and
`funding_ml_carry_portfolio_backtest.simulate_portfolio_equity` (multi-coin ledger, not
single-series).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.domain.services.edge_lifecycle.capital_cert_headline import is_ruin_reason
from src.domain.services.edge_lifecycle.levered_return_book import simulate_levered_return_book
from src.domain.services.edge_lifecycle.return_book_capital_cert import (
    COLLINEAR_WITH_LEVERAGE_AXES,
    INAPPLICABLE_DISCRETE_AXES,
    UNCROSSABLE_AXES,
    certify_return_book_lanes,
)
from src.shared.constants.capital_cert_harness import CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK

LANES = (1, 3, 5, 8)


def _flat(n: int, r: float) -> pd.Series:
    return pd.Series([r] * n, dtype=float)


@pytest.mark.unit
def test_a_survivable_book_reports_every_lane_and_no_liquidation() -> None:
    """The ordinary case: nothing dies, and each lane gets its own capital outcome."""
    cert = certify_return_book_lanes(_flat(50, 0.004), initial_capital=10_000.0, leverages=LANES)

    assert set(cert["lanes"]) == {"spot_10k", "perp_3x", "perp_5x", "perp_8x"}
    assert all(not lane["account_liquidated"] for lane in cert["lanes"].values())
    assert cert["liquidated_lanes"] == []
    assert cert["max_clean_leverage_survived"] == 8
    # leverage scales the PATH: more leverage compounds a positive drift further
    assert cert["lanes"]["perp_8x"]["final_capital"] > cert["lanes"]["spot_10k"]["final_capital"]


@pytest.mark.unit
def test_a_bar_that_wipes_the_account_liquidates_that_lane_only() -> None:
    """A -40% bar ends a 3x book (1 + 3*-0.40 < 0) while spot survives it.

    This is the number the corpus was missing: without it a levered claim reads as survivable
    because nothing ever asked.
    """
    returns = pd.Series([0.01] * 10 + [-0.40] + [0.01] * 10, dtype=float)

    cert = certify_return_book_lanes(returns, initial_capital=10_000.0, leverages=LANES)

    assert cert["lanes"]["spot_10k"]["account_liquidated"] is False
    assert cert["lanes"]["perp_3x"]["account_liquidated"] is True
    assert cert["lanes"]["perp_3x"]["final_capital"] == 0.0
    assert cert["liquidated_lanes"] == ["perp_3x", "perp_5x", "perp_8x"]
    assert cert["max_clean_leverage_survived"] == 1


@pytest.mark.unit
def test_ruin_is_terminal_so_a_later_rally_cannot_resurrect_the_account() -> None:
    """Post-ruin bars are skipped and COUNTED, never traded."""
    returns = pd.Series([-0.40] + [0.50] * 30, dtype=float)

    cert = certify_return_book_lanes(returns, initial_capital=10_000.0, leverages=(3,))

    lane = cert["lanes"]["perp_3x"]
    assert lane["final_capital"] == 0.0
    assert lane["bars_after_ruin_skipped"] == 30


@pytest.mark.unit
def test_drawdown_is_the_pit_not_the_endpoint() -> None:
    """A book that halves and fully recovers must report the hole it went through."""
    returns = pd.Series([-0.5, 1.0], dtype=float)

    cert = certify_return_book_lanes(returns, initial_capital=10_000.0, leverages=(1,))

    lane = cert["lanes"]["spot_10k"]
    assert lane["final_capital"] == pytest.approx(10_000.0)
    assert lane["max_drawdown_pct"] == pytest.approx(-50.0, abs=0.01)


@pytest.mark.unit
def test_the_discrete_trade_axes_are_declared_inapplicable_not_silently_dropped() -> None:
    """Four of the six money axes are undefined for a book with no entries.

    DCA depth, min-confidence, holding period and exit strategy all presuppose discrete
    trades. Omitting them silently would let a reader believe the full cross-product ran;
    naming them keeps the cert honest about what it is.
    """
    cert = certify_return_book_lanes(_flat(20, 0.001), initial_capital=10_000.0, leverages=(1, 3))

    # `inapplicable_axes` reports EVERY axis this harness cannot cross, and there are two
    # separate causes: four presuppose discrete entries, one is collinear with leverage.
    assert set(cert["inapplicable_axes"]) == set(UNCROSSABLE_AXES)
    assert set(INAPPLICABLE_DISCRETE_AXES) <= set(cert["inapplicable_axes"])
    assert cert["cross_product_complete"] is False
    assert "no discrete entries" in cert["inapplicable_reason"]


@pytest.mark.unit
def test_sizing_is_declared_collinear_with_leverage_not_silently_skipped() -> None:
    """The gap that misled a reader: sizing was in NEITHER the axis list nor the reason.

    `simulate_levered_return_book` compounds `capital *= 1 + leverage * bar_return`, so exposing
    a fraction f of the account gives `1 + f * leverage * bar_return` — arithmetically the lane at
    `f * leverage`. A 50%-sized 6x lane IS the 3x lane, so the ladder already spans the axis and a
    sizing sweep would only relabel cells.

    Before this, `inapplicable_axes` named four discrete axes and the reason mentioned sizing ONLY
    as part of the cross-product this is not — so the honest reading was "sizing was skipped",
    which is what a reader concluded. The cert must say which it is.
    """
    cert = certify_return_book_lanes(_flat(20, 0.001), initial_capital=10_000.0, leverages=(1, 3))

    assert "position_sizing" in cert["inapplicable_axes"]
    assert set(COLLINEAR_WITH_LEVERAGE_AXES) <= set(cert["inapplicable_axes"])
    assert "collinear" in cert["inapplicable_reason"]


@pytest.mark.unit
def test_the_collinearity_claim_is_arithmetically_true() -> None:
    """Not a comment to trust — a half-sized 6x lane must equal the 3x lane, to the cent."""
    returns = pd.Series([0.01, -0.02, 0.03, -0.005, 0.012], dtype=float)

    half_of_six = simulate_levered_return_book(returns, initial_capital=10_000.0, leverage=0.5 * 6.0)
    plain_three = simulate_levered_return_book(returns, initial_capital=10_000.0, leverage=3.0)

    assert half_of_six["final_capital"] == plain_three["final_capital"]
    assert half_of_six["max_drawdown_pct"] == plain_three["max_drawdown_pct"]


@pytest.mark.unit
def test_a_non_finite_bar_is_refused_rather_than_treated_as_flat() -> None:
    """A data gap silently read as 0% is how a book flatters itself."""
    returns = pd.Series([0.01, float("nan"), 0.01], dtype=float)

    with pytest.raises(ValueError, match="non-finite"):
        certify_return_book_lanes(returns, initial_capital=10_000.0, leverages=(1,))


@pytest.mark.unit
def test_cost_is_charged_on_the_levered_notional() -> None:
    """Fees accrue on the position held, not on the equity behind it."""
    free = certify_return_book_lanes(_flat(30, 0.002), initial_capital=10_000.0, leverages=(5,))
    costed = certify_return_book_lanes(_flat(30, 0.002), initial_capital=10_000.0, leverages=(5,), cost_per_bar=0.0005)

    assert costed["lanes"]["perp_5x"]["final_capital"] < free["lanes"]["perp_5x"]["final_capital"]


@pytest.mark.unit
def test_a_lane_that_decayed_to_nothing_is_no_longer_counted_as_survived() -> None:
    """A near-total loss is RUIN, not survival — reversing what this test used to pin.

    WHAT IT PINNED BEFORE, AND WHY. The earlier version asserted `max_clean_leverage_survived == 3`
    for exactly this input, arguing: a lane can decay to near-nothing while `account_liquidated`
    stays False, that is literally true, and choosing a ruin floor is a GATE decision belonging to
    the promote gate rather than to this measurement. What this function owed was the honest PAIR —
    survival AND the drawdown beside it — so a caller could never read the flag as permission.

    WHAT REFUTED IT. The pair is not what travels. Measured across the hunt corpus on 2026-08-20:
    **317 of 323 lane certs named a `max_clean_leverage_survived` whose lane had LOST money, 307 of
    those had lost >99%, and many read exactly -100.00%.** The scalar is stamped into artifacts and
    read alone — `ml-gate-leverage-capital-cert.md` even names MAX-CLEAN-LEVERAGE-SURVIVED as part
    of the required cert shape. A field named "clean" and "survived" is a verdict word; emitting one
    was already a policy call, just made with a worse rule than the SoT's.

    THE ORIGINAL ARGUMENT IS HONOURED, NOT DISCARDED: no floor is invented here. This calls
    `capital_cert_headline.headline_exclusion_reason`, the same screen the promote gate uses, which
    is the module the earlier reasoning pointed at.

    -30% for 12 bars ruins BOTH lanes — spot compounds to $138 of $10,000 at a -98.6% drawdown — so
    the honest answer is None: no leverage survived this book, including no leverage at all.
    """
    decay = pd.Series([-0.30] * 12, dtype=float)

    cert = certify_return_book_lanes(decay, initial_capital=10_000.0, leverages=(1, 3))

    lane = cert["lanes"]["perp_3x"]
    # Was `is False` under the old engine — no SINGLE bar drove equity to zero, so the account
    # "survived" at a fraction of a cent. Terminal ruin now ends it at the wipe line instead.
    assert lane["account_liquidated"] is True
    assert lane["final_capital"] == 0.0
    assert lane["max_drawdown_pct"] < -99.0
    assert is_ruin_reason(lane["ruin_reason"]) is True

    # spot is ruined too here, so there is NO surviving lane -- None, never 0 or 1, because both of
    # those read as "a lane survived" to a caller doing a truthiness or numeric comparison.
    assert cert["lanes"]["spot_10k"]["final_capital"] < 200.0
    assert cert["max_clean_leverage_survived"] is None


@pytest.mark.unit
def test_the_cert_declares_which_harness_measured_it() -> None:
    """CERTKEY-2: a lane-only cert must name its own engine, not read as the full combo grid.

    `standing_vrp_always_capital_cert.json` is the only artifact on disk that stamps a harness
    today (`levered_return_book`, hand-assembled in `vrp_capital_cert.py`). This function is the
    domain-layer SoT for that exact measurement, so it must carry the same declaration from the
    shared constant, not a second hardcoded copy of the string.
    """
    cert = certify_return_book_lanes(_flat(20, 0.001), initial_capital=10_000.0, leverages=(1, 3))

    assert cert["harness"] == CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK


@pytest.mark.unit
def test_an_all_liquidating_book_reports_no_surviving_leverage() -> None:
    """`max_clean_leverage_survived` must be None when even spot is wiped, not 0 or 1."""
    returns = pd.Series([-1.5], dtype=float)

    cert = certify_return_book_lanes(returns, initial_capital=10_000.0, leverages=LANES)

    assert cert["max_clean_leverage_survived"] is None
    assert cert["lanes"]["spot_10k"]["account_liquidated"] is True


@pytest.mark.unit
def test_a_lane_that_bleeds_to_nothing_is_ruined_even_though_no_single_bar_liquidated_it() -> None:
    """A slow bleed to $0.00 is ruin, and must not be reported as the max CLEAN leverage.

    Measured across the hunt corpus before this test existed: 317 of 323 lane certs named a
    `max_clean_leverage_survived` whose lane had LOST money, and 307 of those had lost >99% --
    many reading exactly -100.00%. The mechanism is in `simulate_levered_return_book`: it only
    sets `account_liquidated` when a SINGLE bar drives equity <= 0 (needs r <= -1/L). A book that
    decays multiplicatively never trips that, so 8x could bleed $10,000 down to $0.004, round to
    `final_capital: 0.0`, and still be counted as a lane that "survived cleanly".

    -0.5% per bar for 300 bars liquidates nothing at any lane (0.04 < 1 even at 8x), but the
    levered lanes are wiped: spot keeps ~$2.2k while 3x/5x/8x end at ~$107/$5/$0.
    """
    cert = certify_return_book_lanes(_flat(300, -0.005), initial_capital=10_000.0, leverages=LANES)

    # RETARGETED when ruin became terminal. This originally asserted the lane was NOT liquidated,
    # which was a true fact about the OLD engine: only a single bar with `leverage * r <= -1` ended
    # an account, so a slow bleed to $0.004 kept "surviving". The engine now stops at the same wipe
    # line the screen judges by, so the lane reports its own death instead of decaying in silence.
    # The POINT of the test is unchanged and still asserted below: a destroyed lane must never be
    # counted as the max CLEAN leverage.
    assert cert["lanes"]["perp_8x"]["account_liquidated"] is True
    assert cert["lanes"]["perp_8x"]["final_capital"] == 0.0

    # spot lost money too, but it is not RUINED -- it keeps ~22% of the account
    assert cert["lanes"]["spot_10k"]["final_capital"] > 2_000.0
    assert cert["max_clean_leverage_survived"] == 1


@pytest.mark.unit
def test_every_lane_carries_the_sot_ruin_vocabulary_so_the_screen_can_actually_see_it() -> None:
    """The lane must speak `liquidation_exits` / `max_drawdown`, not only its own dialect.

    `capital_cert_headline.headline_exclusion_reason` is the corpus-wide ruin SoT, and it reads
    `liquidation_exits` and `max_drawdown` (a FRACTION, wiped at <= -0.95). This module emitted
    `account_liquidated` and `max_drawdown_pct` (a PERCENT), so handing it a raw lane returned
    "eligible" for every lane -- a silent no-op, and the flattering answer by default.
    """
    cert = certify_return_book_lanes(_flat(300, -0.005), initial_capital=10_000.0, leverages=LANES)

    wiped = cert["lanes"]["perp_8x"]
    # Was 0 under the old engine (a bleed was not a liquidation); now the bleed IS terminal ruin.
    assert wiped["liquidation_exits"] == 1
    assert wiped["max_drawdown"] == pytest.approx(wiped["max_drawdown_pct"] / 100.0, abs=1e-9)
    assert wiped["max_drawdown"] <= -0.95
    assert is_ruin_reason(wiped["ruin_reason"]) is True

    survivor = cert["lanes"]["spot_10k"]
    assert is_ruin_reason(survivor["ruin_reason"]) is False


@pytest.mark.unit
def test_a_losing_but_unruined_lane_still_counts_as_survived() -> None:
    """SURVIVAL IS NOT GROWTH -- do not over-tighten this into "the lane must make money".

    The SoT deliberately DISCLOSES deep drawdown and screens only the wipe (<= -95%), because a
    control that kills a -30% book also kills the survivors. A lane that ends down 26% took no
    liquidation and is not ruined, so it is still the max clean leverage.
    """
    cert = certify_return_book_lanes(_flat(100, -0.003), initial_capital=10_000.0, leverages=(1,))

    lane = cert["lanes"]["spot_10k"]
    assert lane["final_capital"] < 10_000.0
    assert lane["max_drawdown"] > -0.95
    assert cert["max_clean_leverage_survived"] == 1
