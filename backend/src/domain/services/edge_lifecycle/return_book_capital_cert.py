"""Leverage certification for a CONTINUOUS return book — the hypothesis route's missing gate.

WHY THIS EXISTS. Measured 2026-08-19 over the whole hunt corpus: 397 of 397 cells that assert a
leveraged beats-buy-and-hold claim carry ``liquidation_exits: null``. Not "zero liquidations" —
never computed. ``ml-gate-leverage-capital-cert.md`` forbids concluding KILL/NULL from a
spot-only gate, so every one of those verdicts is incomplete rather than wrong, which is a large
and quiet hole in the corpus.

The cause is structural, not an oversight. ``run_edge_capital_x_exit_grid.py`` is the
cross-product engine and keys on ``SYMBOL:TF:VERSION:TYPE`` — a persisted ModelSpec directory. A
hunt-loop cell fits in memory per fold and never writes one, so no spelling of that argument can
reach it. The gap is an input boundary, not a missing join or a stale index.

WHAT THIS DOES NOT CLAIM. Four of the six money axes are UNDEFINED for a book with no discrete
entries: DCA depth, min-confidence, holding period and exit strategy all presuppose trades. This
crosses the ones that ARE defined (leverage, and cost charged on the levered notional) and states
the rest as inapplicable rather than omitting them, so a reader cannot mistake the result for the
full grid. ``cross_product_complete`` is False on purpose and is not a defect to be "fixed" by
inventing values for axes the book does not have.

Sizing is deliberately absent as a separate axis: for a continuous book, deploying fraction ``f``
at leverage ``L`` is arithmetically identical to leverage ``f*L``, so listing both would
double-count one degree of freedom and inflate the apparent size of the search — the selection
error this corpus has already paid for four times.

REUSE: ``simulate_levered_return_book`` already owns the honesty properties this needs — leverage
scales the PATH, drawdown is marked every bar, ruin is terminal, non-finite input is refused. This
module crosses it over lanes and summarises; it re-implements none of the maths.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final

from src.domain.services.edge_lifecycle.capital_cert_headline import (
    headline_exclusion_reason,
    is_ruin_reason,
)
from src.domain.services.edge_lifecycle.levered_return_book import simulate_levered_return_book
from src.shared.constants.capital_cert_harness import CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK

if TYPE_CHECKING:  # pandas only needed for the annotation — keep the domain import light
    import pandas as pd

#: Axes that presuppose discrete entries and therefore cannot be crossed for a continuous book.
INAPPLICABLE_DISCRETE_AXES: Final[tuple[str, ...]] = (
    "dca_depth",
    "min_confidence",
    "holding_period",
    "exit_strategy",
)

#: Axes with NO degree of freedom left once the leverage ladder has been walked — a different
#: reason from the discrete ones above, and worth naming separately so a reader is not left to
#: guess which applies.
#:
#: ``simulate_levered_return_book`` compounds ``capital *= 1 + leverage * bar_return``. Exposing
#: only a fraction ``f`` of the account would give ``1 + f * leverage * bar_return``, which is
#: arithmetically the lane at leverage ``f * leverage``. So a 50%-sized 6x lane IS the 3x lane,
#: and the ladder already spans the axis. Sweeping it would re-run cells under new labels.
#:
#: This is TRUE ONLY FOR THE CONTINUOUS BOOK. For a discrete trade book sizing is independent,
#: because per-position margin interacts with ``max_open_positions`` — which is why the
#: cryptobacktest cert sweeps SIZING_SWEEP and this one does not.
COLLINEAR_WITH_LEVERAGE_AXES: Final[tuple[str, ...]] = ("position_sizing",)

#: Every axis this harness cannot cross, whatever the reason. Emitted as ``inapplicable_axes``.
UNCROSSABLE_AXES: Final[tuple[str, ...]] = (
    *INAPPLICABLE_DISCRETE_AXES,
    *COLLINEAR_WITH_LEVERAGE_AXES,
)

_INAPPLICABLE_REASON: Final[str] = (
    "continuous per-bar return book — no discrete entries, so DCA depth, min-confidence, "
    "holding period and exit strategy have nothing to vary. position_sizing is inapplicable for "
    "a DIFFERENT reason: it is collinear with leverage here, because the book compounds "
    "1 + leverage * return, so exposing a fraction f of the account is arithmetically the lane at "
    "leverage f * leverage — a 50%-sized 6x lane IS the 3x lane, and the ladder already spans it. "
    "Reported as inapplicable rather than omitted, so this is not read as the full leverage x DCA "
    "x confidence x hold x exit x sizing cross-product, and so a reader does not conclude sizing "
    "was simply skipped."
)

_SPOT_LANE: Final[str] = "spot_10k"


def lane_name(leverage: float) -> str:
    """Lane key for a leverage multiple, matching ``best_by_capital_lane``'s spelling."""
    if float(leverage) <= 1.0:
        return _SPOT_LANE
    as_int = int(leverage)
    return f"perp_{as_int}x" if as_int == leverage else f"perp_{leverage:g}x"


#: Why a lane carries no funding cost. Perpetual funding is the largest term in a high-leverage
#: outcome and it is SIGNED — a long pays it, a short receives it — so a lane that does not know
#: the book's side cannot charge it without inventing a direction.
_FUNDING_NOT_MODELLED_REASON: Final = (
    "perpetual funding not charged: cost_per_bar is 0.0 and this harness receives a return "
    "series with no position side, so the sign of funding is unknown. Measured on BTC over "
    "2021-01-01..2026-08-13, funding alone is worth x0.0091 (long) to x108.08 (short) at 8x "
    "over 1,969 days, so this lane's survival is against the PRICE path only, not against "
    "trading costs."
)


def certify_return_book_lanes(
    returns: pd.Series,
    *,
    initial_capital: float,
    leverages: tuple[float, ...] | list[float],
    cost_per_bar: float = 0.0,
    costs_per_bar: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Compound ``returns`` down every leverage lane and report survivability per lane.

    ``max_clean_leverage_survived`` is the highest leverage the SoT ruin screen
    (``capital_cert_headline.headline_exclusion_reason``) does NOT call ruined, and is ``None``
    when every lane is — deliberately not ``0`` or ``1``, because both of those read as "a lane
    survived" to a caller doing a truthiness or numeric comparison.

    WHY THIS IS NOT "never hit zero" ANY MORE. That was the original rule here, and it was pinned
    deliberately: choosing a ruin floor is a GATE decision, so this module measured and let the
    promote gate decide. The reasoning was coherent and the assumption under it was false — it
    assumed the survival flag would be read WITH the drawdown beside it. It is not. The scalar is
    stamped into artifacts and travels alone.

    What refuted it, measured across the hunt corpus on 2026-08-20: **317 of 323 lane certs named
    a `max_clean_leverage_survived` whose lane had LOST money, 307 of those had lost >99%, and
    many read exactly -100.00%.** The mechanism is in ``simulate_levered_return_book``: ruin is
    only flagged when a SINGLE bar drives equity <= 0 (needs ``r <= -1/L``), so a book that decays
    multiplicatively bleeds $10,000 down to $0.004, rounds to ``final_capital: 0.0``, and still
    counts as a lane that survived cleanly.

    This does NOT mint a fifth ruin policy — it calls the one the corpus already uses, which
    screens liquidation, bankruptcy and the mark-to-market wipe (<= -95%). SURVIVAL IS STILL NOT
    GROWTH: a lane that ends down 30% took no ruin and is still counted, because a control that
    kills a -30% book also kills the survivors. Deep drawdown stays DISCLOSED, on the lane.

    Lanes are evaluated in ascending leverage so ``liquidated_lanes`` reads in the order a reader
    expects (the first lane to die, then everything above it).
    """
    ordered = sorted(float(lev) for lev in leverages)
    lanes: dict[str, dict[str, Any]] = {}
    liquidated: list[str] = []
    max_clean: float | None = None

    for leverage in ordered:
        outcome = simulate_levered_return_book(
            returns,
            initial_capital=initial_capital,
            leverage=leverage,
            cost_per_bar=cost_per_bar,
            costs_per_bar=costs_per_bar,
        )
        key = lane_name(leverage)
        outcome["ruin_reason"] = headline_exclusion_reason(outcome)
        lanes[key] = outcome
        if outcome["account_liquidated"]:
            liquidated.append(key)
        if not is_ruin_reason(outcome["ruin_reason"]):
            max_clean = leverage if max_clean is None else max(max_clean, leverage)

    survived: int | float | None = None
    if max_clean is not None:
        survived = int(max_clean) if float(max_clean).is_integer() else max_clean

    return {
        "harness": CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK,
        "lanes": lanes,
        "liquidated_lanes": liquidated,
        "max_clean_leverage_survived": survived,
        "inapplicable_axes": list(UNCROSSABLE_AXES),
        "inapplicable_reason": _INAPPLICABLE_REASON,
        "cross_product_complete": False,
        "cost_per_bar": float(cost_per_bar),
        # FUNDING, STATED RATHER THAN INFERRED FROM A ZERO.
        #
        # `cost_per_bar: 0.0` reads identically whether funding was measured at zero or never
        # modelled at all, and the difference decides the verdict. Same reasoning as
        # `liquidation_exits: None` one layer up, whose comment says it is "stated rather than
        # omitted, so 'no liquidations' is never read off a field that was simply never
        # populated".
        #
        # MEASURED 2026-08-21 — BTC funding over the corpus window (6,151 intervals, 2,051 days,
        # mean +0.000298/day, positive 85.8% of the time) compounds over 1,969 days to x0.1722
        # for a LONG book at 3x and x5.7973 for a SHORT one; at 8x it is x0.0091 against
        # x108.0836. The same unmodelled term spans ~12,000x on side alone, which makes it the
        # largest single contributor to any high-leverage verdict here.
        #
        # This module does not GUESS the side. Charging a long-shaped drag to a short-carry book
        # would swap an honest gap for a confident wrong number. It reports the gap; the caller
        # that knows the book's positions can pass a real `cost_per_bar`.
        "funding_modelled": bool(cost_per_bar) or costs_per_bar is not None,
        "funding_reason": (None if (cost_per_bar or costs_per_bar is not None) else _FUNDING_NOT_MODELLED_REASON),
    }


__all__ = [
    "COLLINEAR_WITH_LEVERAGE_AXES",
    "INAPPLICABLE_DISCRETE_AXES",
    "UNCROSSABLE_AXES",
    "certify_return_book_lanes",
    "lane_name",
]
