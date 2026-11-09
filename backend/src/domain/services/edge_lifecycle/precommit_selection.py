"""Which grid cell may be PRE-COMMITTED to on select, and which may be confirmed.

REUSE-AUDIT: this composes existing SoT modules and imports every one it names:
  * `capital_cert_headline` (imported) -- owns the screens: headline_survivors, is_thin_sample,
    meets_turnover_floor, MIN_SELECT_TRADES. No screen is redefined here.
  * `capital_selection_rank` (imported) -- owns committable_cells and the rank metric. A private
    copy would fail test_capital_selection_rank.py, which asserts function identity.
  * `gate` (imported) -- owns MIN_TRADES_FOR_SHARPE, the significance bar.
Searched first (search_symbols "best publishable select confirm cell candidates turnover
committable"): the selection logic already exists TWICE -- `run_select_confirm_cert
._best_publishable` and `vrp_select_confirm._best_publishable_lane` -- which is exactly the fork
a shared home prevents, and why this is an extraction rather than a third copy. Not extending
`edge_inventory_capital_selection.py` (picks a best cell from ONE grid by metric, with no
select/confirm phase distinction) or `edge_lab/precommit_window.py` (chooses the window, not the
cell).

ARCHITECTURE_PATTERNS.md, per its own instruction to name the row and the anti-fit: this invokes
NO new pattern. It is a plain extraction to a module, so the anti-fits that matter there --
"Factory: the constructor is one line", "Adapter: an adapter between two things we control" --
do not apply because no indirection is being introduced. The justification is measured, not
aesthetic: the runner is at the 400-line cap and a second copy already exists. "It felt cleaner"
is explicitly not a reason, and is not the reason here.

NAMED FOR THE JOB, not the artifact. An earlier spelling (`capital_cert_selection`) collided on
the tokens `capital`+`cert` with the ~50 `capital_certification.json` DATA artifacts, which reads
to a filename guard as a parallel copy of a cert. This module pre-commits a CELL; it neither
produces nor parses a certification.

WHY IT MOVED OUT OF THE RUNNER: `run_select_confirm_cert.py` sat at ~397 of the 400-line cap
(CODING_STANDARDS section 7), so it could not take another feature -- and the feature it owed was
a turnover floor that scales with the select window instead of sitting flat. Same reasoning the
runner already records for `cell_mar`: "a LIBRARY needs the same rule, and a library importing a
runner script to get it would be backwards."

THE TWO PHASES ASK DIFFERENT QUESTIONS, which is why this is one function with a flag:

* SELECT names a lever tuple and DISCARDS its money, so statistical significance is not owed.
  Demanding it there only shrinks the usable window -- measured: halving v33's 589-day OOS put
  every one of 4,348 select-window survivors under `MIN_TRADES_FOR_SHARPE` and aborted the run.
* CONFIRM publishes its number, so that phase must be thick.

Both still require the cell to be a BOOK: ranking by final-$ alone re-selects low-turnover flukes
that cannot be confirmed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_headline import (
    MIN_SELECT_TRADES,
    headline_survivors,
    meets_turnover_floor,
)
from src.domain.services.edge_lifecycle.cell_measurability import is_thin_sample
from src.domain.services.edge_lifecycle.gate import MIN_TRADES_FOR_SHARPE
from src.shared.math.capital_selection_rank import committable_cells, rank_key_for


def _is_lane(cell_lane: object, pinned: str) -> bool:
    """Match a pinned lane against a cell's lane, INCLUDING its DCA suffix.

    The DCA pass names its lanes `perp_3x_dca3` / `spot_10k_dca3` -- same leverage rung, extra
    averaging-in fills. Exact equality would therefore pin `perp_3x` to the non-DCA pools only,
    which silently reintroduces the narrowing this widening exists to remove: measured on the v42
    pair, `dca_cells` is 11,200 of the 12,807 select cells.

    The suffix is matched, not stripped, so `perp_30x` can never satisfy a `perp_3x` pin.
    """
    if not isinstance(cell_lane, str):
        return False
    return cell_lane == pinned or cell_lane.startswith(f"{pinned}_")


def best_publishable(
    cells: list[dict[str, Any]],
    *,
    require_measurable: bool,
    select_metric: str = "final_capital",
    min_trades: int | None = None,
    lane: str | None = None,
    rank_key: Callable[[str], Any] = rank_key_for,
) -> dict[str, Any] | None:
    """Best liquidation-clean cell, or ``None`` when the pool holds no publishable book.

    ``min_trades`` scales BOTH floors with the caller's own window. Omitted, the flat constants
    stand -- so an existing caller behaves exactly as before until it opts in.

    A flat floor is the defect this parameter exists for. `MIN_SELECT_TRADES` is
    `MIN_TRADES_FOR_SHARPE // 2`, commented "half the significance bar, because the select window
    is roughly half the out-of-sample slice" -- an ad-hoc stand-in for scaling. On a 1d select
    window of ~95 bars a flat 50 demands a trade on more than half of all bars, which no daily
    book does, so the phase returns nothing and the book reads as a failure it never earned.

    ``rank_key`` is injected rather than imported-and-called so the metric stays substitutable in
    tests; it defaults to the shared SoT.

    ``lane`` PINS the pre-commitment to one leverage lane. The lane is the USER'S choice
    (`ml-gate-leverage-capital-cert.md`: a lane that liquidates condemns the LANE, never the
    model), so it is an INPUT to a pre-commitment rather than a dimension to search -- and pinning
    it strictly REDUCES the arm count, which is the direction this module exists to push. Measured
    on 1d lightgbm v42: ranking on final capital commits `perp_4x` and grades the book on that
    lane alone, while `perp_3x` is liquidation-clean and beats B&H on both windows. An absent lane
    yields ``None`` rather than the next-best lane: a silent fallback would publish a book the
    caller never asked for.
    """
    pool = cells if lane is None else [c for c in cells if _is_lane(c.get("lane"), lane)]
    candidates = headline_survivors(pool)
    if require_measurable:
        floor = MIN_TRADES_FOR_SHARPE if min_trades is None else min_trades
        candidates = [c for c in candidates if not is_thin_sample(c, min_trades=floor)]
    else:
        # SELECT: no significance needed, but the cell must still be a BOOK.
        floor = MIN_SELECT_TRADES if min_trades is None else min_trades
        candidates = [c for c in candidates if meets_turnover_floor(c, min_trades=floor)]
        # …and it must not be a lane that only ever produced RUIN. Measured 2026-08-16 across all
        # 13 pre-commitments: >=7x liquidated in 5 of 6 commits, <=6x in 0 of 7, and the highest
        # final capital in the whole table was a perp_5x cell. The liq-clean filter cannot catch
        # this — it judges the SELECT window, and all 5 ruined commits were liq-clean there.
        # SELECT only: CONFIRM must evaluate whatever was committed, ruin included.
        candidates = list(committable_cells(candidates))
    if not candidates:
        return None
    return max(candidates, key=rank_key(select_metric))


def select_winners(
    cells: list[dict[str, Any]],
    *,
    select_lane: str,
    ladder: tuple[str, ...],
    select_metric: str = "final_capital",
    min_trades: int | None = None,
    rank_key: Callable[[str], Any] = rank_key_for,
) -> tuple[tuple[str | None, ...], dict[str | None, dict[str, Any]]]:
    """The SELECT step of a pre-commitment: the book's own pick plus one cell per committable rung.

    LADDER-SELECT-1 (2026-09-24): an unpinned run pre-commits the pick (key ``None``) AND one cell
    per rung of ``ladder``, all from this one select pool; a pinned ``select_lane`` commits only that
    lane. A rung with no publishable cell is left out -- never filled from another lane. A lane is
    the user's choice, so enumerating the rungs adds no selection arm; picking the best rung would.

    Returns ``(rungs, winners)``; ``rungs[0]`` is the commitment that owns the book's record.
    One home for both routes: `run_select_confirm_cert.main` (a ModelSpec) and the hypothesis
    pre-commit runners (PINE-LOGIT-LONG-MONEY-1), so the two can never select differently.
    """
    rungs: tuple[str | None, ...] = (select_lane,) if select_lane else (None, *ladder)
    winners: dict[str | None, dict[str, Any]] = {}
    for lane in rungs:
        winner = best_publishable(
            cells,
            require_measurable=False,
            select_metric=select_metric,
            min_trades=min_trades,
            lane=lane,
            rank_key=rank_key,
        )
        if winner is not None:
            winners[lane] = winner
    return rungs, winners


__all__ = ["best_publishable", "select_winners"]
