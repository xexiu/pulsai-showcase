"""What a SELECT window is allowed to rank on. The rule, in one place.

REUSE-AUDIT: this is a MOVE, not a new capability. `cell_mar`, `SELECT_METRICS` and `rank_key_for`
shipped in `src/research/edge_hunt/run_select_confirm_cert.py` (042392986) and are lifted here
verbatim so a LIBRARY (`portfolio_capital_matrix`) can call them without importing a runner script.
The runner now imports them from here; `test_capital_selection_rank.py` asserts function IDENTITY,
so a copy-paste back into either caller fails the suite instead of drifting.
Considered and rejected: `edge_inventory_cryptobacktest_helpers.pick_best_cell` (ML grid cells with
exits/DCA/confidence, a different shape) and `rerank_edge_capital_x_exit.py` (a one-off re-rank of
one artifact).

## Why a rule needs a home

Owner, 2026-08-14, after eight days: *"tomorrow you will say use this logic and that logic and
output will be different than yesterday"*. A selection rule that lives inside whichever script ran
last makes every number incomparable. It lives here, and the tests are what make changing it a
decision rather than a drift.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any, Final, TypeVar

#: One grid cell, as READ. Bound to `Mapping` because nothing here mutates a cell.
#:
#: It is a TypeVar rather than a bare `Mapping[str, Any]` so that the two FILTERS below return the
#: same concrete type they were handed: `list[dict[str, Any]]` in gives `list[dict[str, Any]]` out.
#: A bare Mapping return silently downgrades every caller's element type just for filtering, and
#: the caller then has to widen its own annotations to match — pushing an artifact of this module's
#: signature outward into unrelated code. Filters preserve; only transforms change the type.
CellT = TypeVar("CellT", bound=Mapping[str, Any])

#: What SELECT may rank on. Closed on purpose — see `rank_key_for`.
SELECT_METRICS: Final[tuple[str, ...]] = ("final_capital", "mar")
#: Default for admin doors + workers — bind this, never a second ``"final_capital"`` literal.
DEFAULT_SELECT_METRIC: Final[str] = SELECT_METRICS[0]

#: The highest leverage a PRE-COMMITMENT may commit to.
#:
#: MEASURED 2026-08-16 across all 13 `select_confirm_*` artifacts, by the lane actually committed:
#:
#:     >= 7x   6 commits   5 LIQUIDATED (83%)   best liq-clean final $12,815
#:     <= 6x   7 commits   0 liquidated  (0%)   best liq-clean final $17,131
#:
#: Zero counterexamples on the low side. Every liquidation in the corpus — 32 liquidation exits
#: across 5 books, two accounts taken to $0 — came from a `perp_7x` or `perp_8x` commit. And the
#: leverage bought nothing: the HIGHEST final capital in the whole table is a `perp_5x` cell
#: (v33, $17,131), beating every >=7x cell that survived. prod v2's own pre-commitment chose
#: `perp_7x` and liquidated NINE times while reading "+162% profitable".
#:
#: So this is not a risk preference. On the measured corpus it removes 100% of observed ruin while
#: giving up nothing, because the best book was never a high-leverage one.
#:
#: WHY THE EXISTING LIQ-CLEAN FILTER IS NOT ENOUGH: the cert already drops liquidating cells, but it
#: does so AFTER seeing the window. A pre-commitment must choose on SELECT and live with CONFIRM —
#: and all 5 ruined commits were liq-clean ON THE SELECT WINDOW when they were chosen. The lane is
#: the only handle available before the outcome is known.
#: LOWERED 6 -> 5 on 2026-08-16, same day it shipped, by the two pre-commitments that followed:
#:
#:     v33  committed perp_6x  ->  liquidated 2x, ended $9,847
#:     v11  committed perp_6x  ->  liquidated 5x, ACCOUNT BANKRUPT, $0 from $10,000
#:
#: The original 6 came from 13 pre-commitments where <=6x liquidated 0 of 7 — a sample that happened
#: to contain no 6x commit at all, so the boundary was never tested there. It has now been tested
#: twice and failed twice, once with total ruin.
#:
#: Both books had a liquidation-clean lane in the SAME grid that the selector skipped: v11's perp_3x
#: returned 2.92x B&H on 408 trades at -23.1% with ZERO liquidating cells in the lane, while perp_6x
#: carried 195 of ~410. The selector ranks on final capital at the SELECT window, so it climbs the
#: leverage ladder toward the biggest number and cannot see that the lane it lands in is riddled
#: with ruin. Capping the committable lane is the ex-ante handle; a post-hoc liq-clean filter cannot
#: help, because both cells were liq-clean ON THEIR SELECT WINDOW when chosen.
MAX_COMMITTABLE_LEVERAGE: Final[int] = 5


def lane_leverage(lane: object) -> int:
    """Leverage multiple a lane name declares. Unparseable or spot reads as 1 (unlevered).

    Reads the FIRST `<n>x` token so a DCA suffix cannot be mistaken for the multiple:
    ``perp_5x_dca3`` is a 5x lane, not a 3x one.
    """
    match = re.search(r"(\d+)\s*x", str(lane or ""), re.IGNORECASE)
    return int(match.group(1)) if match else 1


def lane_safe_cells(cells: Iterable[CellT]) -> list[CellT]:
    """Cells whose ENTIRE LANE is free of liquidation and bankruptcy, in original order.

    The cell-level liquidation filter cannot prevent a ruinous pre-commitment, because a ruinous
    lane still contains liquidation-clean cells and the selector picks one of them. MEASURED
    2026-08-16 across three certified books: ranking on final capital chose lanes holding 239 / 195
    / 43 liquidating cells, and on the two books whose pre-commitments were run, that lane
    LIQUIDATED — v33 twice, v11 five times with the account bankrupt at $0. Both committed cells
    were liquidation-clean AS CELLS on their own select window, which is exactly why nothing caught
    them.

    MAR does not fix it either (measured): it moves the commit one rung, 6x -> 5x, into a lane still
    holding 99 liquidating cells.

    This asks a different question — is the NEIGHBOURHOOD survivable? — which is knowable ex-ante
    and is what "the account died on the next window" turned out to mean.

        book  current rule           lane-safe pick         xB&H
        v33   perp_8x (239 liq)  ->  perp_3x (0 liq)        13.23 -> 6.01
        v11   perp_6x (195 liq)  ->  perp_3x (0 liq)         1.78 -> 3.93
        v10   perp_6x  (43 liq)  ->  perp_3x_dca3 (0 liq)    2.89 -> 0.91

    The v10 row is the honest cost: on a book whose edge needs leverage, demanding a ruin-free
    neighbourhood can leave nothing that beats buy-and-hold.

    NOT WIRED, AND NOT BECAUSE THE TEST IS STILL OWED. This paragraph used to end "a three-book
    hypothesis owed a confirm-window test, not a shipped rule", and that was already false when
    read on 2026-09-15: the test was RUN as a real forward pre-commitment on v11 the same week,
    and the rule FAILED — confirm $426 from $10,000, 0.07x B&H, maxDD -99.1%, an
    `mtm_drawdown_wipe` reached without tripping `liquidation_exits` or `account_bankrupt`. Lane
    safety swapped a bankruptcy for a wipe; both are accounts the user lost. The full record,
    including the two sibling rules that failed the same day, is the class docstring of
    `TestLaneSafeSelection` in `tests/unit/shared/math/test_committable_lane_cap.py`.

    So this is a FALSIFIED rule kept as a tested predicate, not a pending one. The distinction is
    load-bearing: "owed a test" invites the next reader to run it and wire it, which is the exact
    move that already cost two ruined accounts.

    TWO SEPARATE REASONS NOT TO WIRE IT, and the second outlives any re-test:

    1. It lost its forward test (above).
    2. It is INERT at the call site anyway. `best_publishable` applies its filters to the output of
       `headline_survivors`, which removes liquidating and bankrupt cells — the very evidence this
       function reads — so the ruined-lane set would always be empty. Measured by replaying SELECT
       over all 42 `select_confirm_*` artifacts: an identical pick on 42 of 42 books. Pinned by
       `TestLaneSafetyReadsEvidenceTheCellScreenDeletes`. Anyone wiring it here ships a no-op that
       reads as a risk control; it would have to run against the RAW pool to mean anything.

    A retrospective re-pick over the frozen grids does favour it (ruin 11 -> 6 across those 42
    books, at a cost of 2 money books and 11 refusals-to-commit). That is BACKWARD evidence of
    exactly the kind that put `MAX_COMMITTABLE_LEVERAGE = 6` in this file and was falsified twice
    within a day. It is recorded here so the next person does not mistake it for new support.
    """
    pool = list(cells)
    ruined = {cell.get("lane") for cell in pool if int(cell.get("liquidation_exits") or 0) > 0 or cell.get("account_bankrupt")}
    return [cell for cell in pool if cell.get("lane") not in ruined]


def committable_cells(cells: Iterable[CellT]) -> list[CellT]:
    """Cells a pre-commitment may choose from, in their original order.

    Returns EMPTY when every candidate is over the cap — deliberately no fallback. Falling back to
    the best over-cap cell is the exact failure being fixed: it is how `perp_7x` reached prod v2's
    confirm window and liquidated nine times.
    """
    return [cell for cell in cells if lane_leverage(cell.get("lane")) <= MAX_COMMITTABLE_LEVERAGE]


def cell_mar(cell: Mapping[str, Any]) -> float | None:
    """MAR = return / |max drawdown|. None when the question cannot be answered.

    None -- never a sentinel like 0 or inf -- for a missing/zero drawdown or a losing cell. A cell
    with no recorded DD has UNKNOWN risk, not zero risk, and ranking it as infinitely good is how
    an unmeasured cell wins a selection it should never have entered.
    """
    try:
        initial = float(cell["initial_capital"])
        final = float(cell["final_capital"])
        dd = float(cell["max_drawdown"])
    except KeyError, TypeError, ValueError:
        return None
    if initial <= 0 or dd == 0 or final <= initial:
        return None
    return (final / initial - 1.0) / abs(dd)


def rank_key_for(metric: str) -> Any:
    """Sort key for a SELECT metric. Raises on an unknown name.

    Refusing beats defaulting: a typo silently reverting to `final_capital` would republish the
    exact defect this exists to fix -- and it would look like it had worked.

    MEASURED, 2026-08-11 (`1d gb v10`, 44 liquidation-clean profitable cells): ranking on
    `final_capital` selects +71.3% at **-72.3%** DD; ranking on `mar` selects +19.1% at
    **-20.9%** DD over 131 trades, still beating buy-and-hold. Same signal, a third of the
    drawdown. Money-ranking always picks the most levered survivor, because leverage IS the
    ranking.

    The `mar` key is a TUPLE, `(mar, final_capital)`. Every MAR on an all-losing ladder is None, so
    a scalar key would leave `max` returning whichever cell the dict happened to yield first --
    a rule whose answer depends on iteration order, which is the "different answer tomorrow" this
    module exists to end. The second element only ever breaks ties.
    """
    if metric not in SELECT_METRICS:
        raise ValueError(f"unknown select metric {metric!r} — expected one of {SELECT_METRICS}")
    if metric == "mar":
        return lambda c: (
            cell_mar(c) if cell_mar(c) is not None else -math.inf,
            float(c.get("final_capital") or 0.0),
        )
    return lambda c: float(c.get("final_capital") or 0.0)


__all__ = [
    "DEFAULT_SELECT_METRIC",
    "MAX_COMMITTABLE_LEVERAGE",
    "SELECT_METRICS",
    "cell_mar",
    "committable_cells",
    "lane_leverage",
    "lane_safe_cells",
    "rank_key_for",
]
