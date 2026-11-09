"""A pre-commitment may not commit to a lane that only ever produced ruin.

MEASURED 2026-08-16 across all 13 `select_confirm_*` artifacts, by the lane the selector committed:

    >= 7x   6 commits   5 LIQUIDATED (83%)   best liq-clean final $12,815
    <= 6x   7 commits   0 liquidated  (0%)   best liq-clean final $17,131

Zero counterexamples on the low side. All 32 liquidation exits across 5 books -- including two
accounts taken to $0 -- came from a perp_7x or perp_8x commit. And the leverage bought NOTHING: the
highest final capital in the whole pre-commitment table is a perp_5x cell (v33, $17,131), beating
every >=7x cell that survived.

WHY A CAP AND NOT THE EXISTING LIQ-CLEAN FILTER. The cert headline already drops liquidating cells,
but it does so AFTER seeing the window. A pre-commitment must choose on SELECT and live with the
result on CONFIRM, so "was it liq-clean on select?" does not predict ruin on confirm -- every one of
these 5 ruined commits was liq-clean when it was chosen. The lane is the only ex-ante handle.

REUSE-AUDIT: extends `capital_selection_rank` (already the shared home for SELECT ranking rules,
imported by both the runner and `portfolio_capital_matrix`) rather than adding a second selection
module. Considered putting it in `capital_cert_headline` -- rejected, that filter is post-hoc and
applies to headlines, not to what a pre-commitment may commit to.
"""

from __future__ import annotations

import ast
from pathlib import Path

from src.domain.services.edge_lifecycle import precommit_selection
from src.domain.services.edge_lifecycle.capital_cert_headline import headline_survivors
from src.shared.math.capital_selection_rank import (
    MAX_COMMITTABLE_LEVERAGE,
    committable_cells,
    lane_leverage,
    lane_safe_cells,
)


class TestLaneLeverageIsReadFromTheLaneName:
    def test_spot_is_unlevered(self) -> None:
        assert lane_leverage("spot_10k") == 1

    def test_a_perp_lane_reports_its_multiple(self) -> None:
        assert lane_leverage("perp_5x") == 5
        assert lane_leverage("perp_8x") == 8

    def test_a_dca_suffix_does_not_hide_the_leverage(self) -> None:
        """`perp_5x_dca3` is still a 5x lane — the DCA depth must not be read as the multiple."""
        assert lane_leverage("perp_5x_dca3") == 5

    def test_an_unparseable_lane_is_treated_as_unlevered(self) -> None:
        """Fail OPEN on the leverage read: a lane we cannot parse must not be silently barred."""
        assert lane_leverage("") == 1
        assert lane_leverage(None) == 1


class TestTheCapMatchesTheMeasuredRuinBoundary:
    def test_the_cap_is_five(self) -> None:
        """Lowered 6 -> 5 the same day 6 shipped: v33 committed perp_6x and liquidated 2x; v11
        committed perp_6x and went BANKRUPT at $0. Two independent books, both ruined at 6x."""
        assert MAX_COMMITTABLE_LEVERAGE == 5

    def test_the_lanes_that_never_ruined_are_committable(self) -> None:
        for lane in ("spot_10k", "perp_3x", "perp_5x", "perp_5x_dca3"):
            assert committable_cells([{"lane": lane}]) == [{"lane": lane}], lane

    def test_the_lanes_that_ruined_are_not_committable(self) -> None:
        assert committable_cells([{"lane": "perp_6x"}, {"lane": "perp_7x"}, {"lane": "perp_8x"}]) == []


class TestItFiltersAPoolWithoutReorderingIt:
    def test_only_the_over_cap_cells_are_dropped(self) -> None:
        pool = [
            {"lane": "perp_8x", "final_capital": 99_999},
            {"lane": "perp_5x", "final_capital": 17_131},
            {"lane": "spot_10k", "final_capital": 11_080},
        ]

        assert committable_cells(pool) == [pool[1], pool[2]]

    def test_an_empty_pool_stays_empty(self) -> None:
        assert committable_cells([]) == []

    def test_a_pool_of_only_over_cap_lanes_yields_nothing_rather_than_falling_back(self) -> None:
        """No silent fallback: if every candidate is over the cap there is NO safe commitment.

        Falling back to the best over-cap cell is exactly the failure being fixed — it is how
        `perp_7x` reached prod v2's confirm window and liquidated nine times.
        """
        assert committable_cells([{"lane": "perp_7x"}, {"lane": "perp_50x"}]) == []


class TestLaneSafeSelection:
    """FALSIFIED as a selection rule — kept as a tested predicate, deliberately NOT wired.

    The idea: SELECT should not commit to a cell whose LANE is riddled with ruin. On backward
    evidence it looked like the only rule that helped — the current selector picked lanes holding
    239 / 195 / 43 liquidating cells, and lane-safety reached `perp_3x` on both books that died.

    THEN IT WAS RUN AS A REAL PRE-COMMITMENT (v11, 2026-08-16), which is the only test that counts:

        select 2023-07-12 -> 2025-06-01   commit perp_3x / hold / conf65 / hold3
        confirm 2025-06-01 -> 2026-08-16  final $426 from $10,000 · 0.07x B&H · maxDD -99.1%

    That is `mtm_drawdown_wipe` — RUIN by this project's own definition (`capital_cert_headline`
    `RUIN_REASONS`), reached WITHOUT tripping `liquidation_exits` or `account_bankrupt`. Lane-safety
    swapped a bankruptcy for a wipe. Both are accounts the user lost.

    Three ex-ante lever-selection rules were tested on v11 in one day and ALL THREE ruined the
    confirm window: the 6x lane cap (bankrupt, $0), MAR ranking (one rung down, into a lane with 99
    liquidating cells), and lane-safety (wiped, $426). The consistent answer is that v11's problem is
    NOT which lever is chosen — the book does not survive leverage out-of-sample, and no selection
    rule repairs a book with no edge to select from.

    Why the code stays: the predicate is correct and cheap, the measurement above is what makes the
    negative result citable, and deleting it guarantees the idea gets re-invented. Wiring it would
    repeat the exact error that put `MAX_COMMITTABLE_LEVERAGE = 6` in this file and cost two ruined
    accounts before the day was out — shipping a selection rule on backward evidence alone.
    """

    def test_a_lane_with_any_liquidating_cell_is_not_safe(self) -> None:
        cells = [
            {"lane": "perp_6x", "final_capital": 90_000, "liquidation_exits": 0},
            {"lane": "perp_6x", "final_capital": 10_000, "liquidation_exits": 3},
            {"lane": "perp_3x", "final_capital": 30_000, "liquidation_exits": 0},
        ]

        assert lane_safe_cells(cells) == [cells[2]]

    def test_the_clean_cell_of_a_dirty_lane_is_still_excluded(self) -> None:
        """The 90k cell is itself liq-clean — that is exactly the trap the cell filter misses."""
        cells = [
            {"lane": "perp_6x", "final_capital": 90_000, "liquidation_exits": 0},
            {"lane": "perp_6x", "final_capital": 10_000, "liquidation_exits": 5},
        ]

        assert lane_safe_cells(cells) == []

    def test_a_bankrupt_cell_also_condemns_its_lane(self) -> None:
        cells = [
            {"lane": "perp_5x", "final_capital": 50_000, "liquidation_exits": 0},
            {"lane": "perp_5x", "final_capital": 0, "account_bankrupt": True},
        ]

        assert lane_safe_cells(cells) == []

    def test_an_all_clean_pool_is_unchanged(self) -> None:
        cells = [
            {"lane": "spot_10k", "final_capital": 12_000},
            {"lane": "perp_3x", "final_capital": 30_000},
        ]

        assert lane_safe_cells(cells) == cells

    def test_an_empty_pool_stays_empty(self) -> None:
        assert lane_safe_cells([]) == []


class TestLaneSafetyReadsEvidenceTheCellScreenDeletes:
    """The trap waiting for whoever wires this rule after all: it is INERT in the obvious place.

    Every filter in `best_publishable` is applied to the pool returned by `headline_survivors`.
    Put lane-safety there and it does nothing at all, because `headline_exclusion_reason` removes
    liquidating and bankrupt cells -- precisely the evidence lane-safety exists to read. The
    ruined-lane set it computes over an already-screened pool is EMPTY by construction.

    MEASURED 2026-09-15 by replaying the SELECT rule over all 42 `select_confirm_*` artifacts
    against their own grids on disk: inserting `lane_safe_cells` after the screen produced an
    IDENTICAL pick on 42 of 42 books. Not "rarely changes anything" -- never changes anything.

    That matters even though the rule is deliberately unwired (see the class above), because the
    docstring there predicts the idea gets re-invented, and the re-inventor's natural call site is
    the one that silently cannot work. A no-op that reads as a shipped risk control is worse than
    an absent one.

    The five tests above all hand the function a pool that still CONTAINS its liquidating cells --
    which is the one thing the production call site can never hand it. That is why the no-op was
    invisible to a green suite.
    """

    #: One ruinous lane and one clean lane. The 90k cell is itself liq-clean, so the CELL screen
    #: keeps it while the LANE it sits in is the one that ruined.
    RAW_POOL = (
        {"lane": "perp_5x", "final_capital": 90_000, "liquidation_exits": 0, "max_drawdown": -0.2},
        {"lane": "perp_5x", "final_capital": 0, "liquidation_exits": 4, "max_drawdown": -0.9},
        {"lane": "perp_3x", "final_capital": 30_000, "liquidation_exits": 0, "max_drawdown": -0.2},
    )

    def test_the_cell_screen_removes_the_very_evidence_lane_safety_needs(self) -> None:
        raw = [dict(cell) for cell in self.RAW_POOL]

        screened = headline_survivors(raw)

        assert screened == [raw[0], raw[2]], "the liquidating cell is gone, so its lane looks clean"

    def test_lane_safety_is_a_strict_no_op_once_the_screen_has_run(self) -> None:
        """42 of 42 pre-commitments picked the identical cell with this filter inserted here."""
        screened = headline_survivors([dict(cell) for cell in self.RAW_POOL])

        assert lane_safe_cells(screened) == screened

    def test_on_the_raw_pool_it_condemns_the_lane_that_ruined(self) -> None:
        """The same filter, one step earlier, is not inert -- so the call POSITION is the rule."""
        raw = [dict(cell) for cell in self.RAW_POOL]

        assert lane_safe_cells(raw) == [raw[2]]

    def test_the_two_positions_genuinely_disagree(self) -> None:
        """Guard the guard: if these ever coincide, the three tests above prove nothing."""
        raw = [dict(cell) for cell in self.RAW_POOL]

        assert lane_safe_cells(raw) != lane_safe_cells(headline_survivors(raw))


class TestTheSelectorDoesNotWireLaneSafety:
    """A RATCHET, because describing the trap above does not stop anyone walking into it.

    The four tests above pin the BEHAVIOUR of `lane_safe_cells`. None of them pins whether the
    selector CALLS it — so importing it into `precommit_selection` tomorrow leaves the whole suite
    green while shipping a filter that is (a) falsified on its only forward test and (b) inert in
    that exact position. Prose in a docstring cannot fail; this can.

    Two independent reasons the selector must not call it, either one sufficient:

    1. FALSIFIED. Run as a real pre-commitment on v11, it returned $426 from $10,000 at -99.1% DD.
    2. INERT THERE. `best_publishable` filters the output of `headline_survivors`, which has already
       removed the liquidating and bankrupt cells that are its only evidence — an identical pick on
       42 of 42 pre-commitments.

    If a future measurement genuinely justifies lane-safe selection, this test is the place that
    records the decision: change it deliberately, with the forward evidence in the commit, rather
    than by adding an import nobody reviews.
    """

    SELECTOR = Path(precommit_selection.__file__)

    def test_the_selector_source_is_actually_readable(self) -> None:
        """Guard the guard: a path that stops resolving would make the ratchet below vacuous."""
        assert self.SELECTOR.is_file(), f"selector module not found at {self.SELECTOR}"
        assert "best_publishable" in self.SELECTOR.read_text(), "not the module this ratchet thinks it is"

    def test_lane_safety_is_not_referenced_by_the_selector(self) -> None:
        tree = ast.parse(self.SELECTOR.read_text())

        referenced = sorted(node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == "lane_safe_cells")
        imported = sorted(
            alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names if alias.name == "lane_safe_cells"
        )

        assert not imported, (
            "precommit_selection imports lane_safe_cells. It is falsified as a selection rule "
            "(v11: $426 from $10,000, -99.1% DD) and inert after headline_survivors (identical "
            "pick on 42 of 42). See TestLaneSafeSelection for the record."
        )
        assert not referenced, "precommit_selection calls lane_safe_cells — see the message above"

    def test_the_selector_does_still_call_the_cap_that_is_wired(self) -> None:
        """Not a blanket ban on this module: the committable-lane cap IS wired, and must stay."""
        source = self.SELECTOR.read_text()

        assert "committable_cells" in source, "the 5x cap vanished from the selector — that IS wired"
