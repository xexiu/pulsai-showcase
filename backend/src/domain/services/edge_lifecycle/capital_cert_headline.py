"""Headline eligibility for capital-cert grid cells — which money number may be published.

Owner honesty standard (``.claude/rules/ml-gate-leverage-capital-cert.md``): ranking combo cells by
final ``$`` alone is a trap. The raw money leaders are almost always high-leverage cells that
LIQUIDATE the user, or ALL-IN leveraged cells whose numbers are fantasy. **The drawdown floor does
not catch either** — with fixed per-trade sizing each liquidation loses only that margin, so account
DD can stay shallow while positions are repeatedly wiped.

Two rules, one predicate:

* **Ruin** — any ``liquidation_exits``, ``account_bankrupt``, or an honest mark-to-market drawdown at
  the wipe threshold. A book that liquidates its user is not a money-maker at any final balance.
* **All-in at leverage** — fantasy per the honest-engine correction; a leverage lane counts ONLY at a
  survivable fractional sizing. All-in on SPOT stays eligible: spot cannot liquidate and all-in is
  the product default.

WHY a domain module: ``run_edge_capital_x_exit_grid`` implemented this twice and the copies
disagreed — the bounded coord-descent ``accept()`` barred all-in and ruin, while the exhaustive
path's ``_survivors()`` barred ruin only, so the published headline could still be an all-in
leveraged cell. Both paths now share this SoT. Pure rules, no I/O (DDD_PATTERNS).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any, Final, TypeVar

from src.domain.services.edge_lifecycle.cell_measurability import is_thin_sample
from src.domain.services.edge_lifecycle.gate import MIN_TRADES_FOR_SHARPE

#: Any grid cell shape the screens can read — a plain dict, a ``Mapping`` row, or a TypedDict.
_CellT = TypeVar("_CellT", bound=Mapping[str, Any])

ALL_IN_SIZING: Final = "all_in"

# An honest MTM drawdown this deep means the account was wiped intrabar even if no single position
# crossed its liquidation PRICE and the bankruptcy flag missed it.
DRAWDOWN_WIPE_THRESHOLD: Final = -0.95

EXCLUDED_LIQUIDATED: Final = "liquidated"
EXCLUDED_BANKRUPT: Final = "account_bankrupt"
EXCLUDED_DRAWDOWN_WIPE: Final = "mtm_drawdown_wipe"

#: Kept as the disclosure's name. It is NO LONGER an exclusion — see `headline_disclosures`.
EXCLUDED_ALL_IN_LEVERAGED: Final = "all_in_leveraged"
DISCLOSURE_ALL_IN_LEVERAGED: Final = EXCLUDED_ALL_IN_LEVERAGED

#: The ONLY reasons that may KILL a book: each one describes an account the user actually LOST.
#: Anything outside this set is a fact to disclose beside the money, never a verdict against it.
RUIN_REASONS: Final = frozenset({EXCLUDED_LIQUIDATED, EXCLUDED_BANKRUPT, EXCLUDED_DRAWDOWN_WIPE})

#: Cell field names this module READS. Exported so a producer stamps the same spelling instead of
#: repeating the literal: `_max_drawdown` wants a FRACTION (-0.989), and a writer that emitted a
#: percent (-98.9) or a differently-named key would sail through every screen as "eligible",
#: because an absent field reads as 0.0 — the flattering default.
CELL_FIELD_LIQUIDATION_EXITS: Final = "liquidation_exits"
#: Where a lane-only cert keeps its per-lane results. Read as a FALLBACK for the flat count.
CELL_FIELD_LEVERAGE_CERT: Final = "leverage_cert"
CELL_FIELD_MAX_DRAWDOWN: Final = "max_drawdown"

#: The RETURN-BOOK lane dialect. Two producers write ruin, and they do not agree on spelling:
#: the cross-product cert writes `liquidation_exits` + `max_drawdown` (a FRACTION), while
#: `levered_return_book` writes `account_liquidated` + `max_drawdown_pct` (a PERCENT). Reading
#: only the first dialect is why 698 lanes sitting at $0.00 read as eligible.
CELL_FIELD_ACCOUNT_LIQUIDATED: Final = "account_liquidated"
CELL_FIELD_MAX_DRAWDOWN_PCT: Final = "max_drawdown_pct"

#: Percent -> fraction. The percent form is CONVERTED, never compared directly: reading -50.0 as
#: though it were a fraction would call a survivable -50% book a wipe.
PERCENT_PER_UNIT: Final = 100.0


def _liquidation_count(cell: Mapping[str, Any]) -> int:
    """The cell's OWN liquidations: its flat count, else its exit-type histogram, else its bool.

    A cell's ``leverage_cert`` lanes are NOT consulted. Each lane is a separate book carrying its
    own ``ruin_reason`` -- "a liquidated perp_8x never condemns a clean perp_3x" (ADR-025 rung 1b)
    -- and a hunt capital block's headline is the UNLEVERED stream the lanes were levered from.
    From 7b850bbf38 (2026-08-21) a None count fell back to summing every lane, so any 3x-8x
    liquidation condemned the clean book. MEASURED 2026-10-09 over 2,236 hunt cells: 1,134 were
    condemned by lanes alone, 954 of them clean on their own record, 301 beating same-window
    buy-and-hold. Ruin of the stream itself stays caught by ``account_bankrupt`` and the wipe.
    """
    raw = cell.get(CELL_FIELD_LIQUIDATION_EXITS)
    if raw is None:
        counts = cell.get("exit_type_counts")
        raw = counts.get("liquidation") if isinstance(counts, Mapping) else None
    try:
        count = int(raw or 0)
    except TypeError, ValueError:
        count = 0
    # A return-book lane carries no count at all — it reports the fact as a bool. A cell that says
    # it liquidated, liquidated, so it counts as at least one however the numeric side reads.
    if cell.get(CELL_FIELD_ACCOUNT_LIQUIDATED) is True:
        return max(count, 1)
    return count


def _cell_drawdown_fraction(cell: Mapping[str, Any]) -> float:
    """The drawdown a cell RECORDED, as a fraction -- a field read; ``block_bootstrap.max_drawdown`` computes one."""
    raw = cell.get(CELL_FIELD_MAX_DRAWDOWN)
    if raw is None:
        # Return-book dialect: a PERCENT. Converted, never compared as-is.
        pct = cell.get(CELL_FIELD_MAX_DRAWDOWN_PCT)
        if pct is None:
            return 0.0
        try:
            return float(pct) / PERCENT_PER_UNIT
        except TypeError, ValueError:
            return 0.0
    try:
        return float(raw)
    except TypeError, ValueError:
        return 0.0


def _is_leveraged(cell: Mapping[str, Any]) -> bool:
    """True unless the cell is demonstrably spot — fails CLOSED on a missing leverage field."""
    raw = cell.get("leverage")
    if raw is not None:
        try:
            return float(raw) > 1.0
        except TypeError, ValueError:
            return True
    return cell.get("spot_mode") is not True


def _is_all_in(cell: Mapping[str, object]) -> bool:
    """True unless the cell records a FRACTIONAL sizing — fails CLOSED on a missing field.

    Symmetric with ``_is_leveraged``: unrecorded is treated as the dangerous case, not the safe
    one. The discovery passes (cross/hold/conf) never stamp ``sizing`` and run at the default
    ALL-IN, so reading a missing field as "not all-in" let $99k all-in 5x cells present themselves
    as publishable the moment those passes were unioned into the headline pool.
    """
    return str(cell.get("sizing") or ALL_IN_SIZING) == ALL_IN_SIZING


def headline_exclusion_reason(cell: Mapping[str, Any]) -> str | None:
    """Why this cell may not be the headline, or ``None`` when it is eligible.

    Every reason returned here is a RUIN reason — the account was actually lost. Sizing is NOT
    one of them; it rides alongside the money via `headline_disclosures`.

    WHY SIZING WAS REMOVED AS A KILL (owner, 2026-08-12: "if a model passes OOS, DSR, IC, makes
    money and beats B&H, then why is it killed?"). Three measured facts, in order of weight:

    1. **It is structurally incapable of catching ruin.** Ruin is tested first and returns early,
       so `all_in_leveraged` only ever fired on a cell that had ALREADY passed all three ruin
       screens. It removed survivors, by construction, and nothing else.
    2. **It does not rank risk.** Measured across the 33 certs on disk: the screen ADMITTED
       `1d gb_clf v10` at a −72.3% drawdown and REJECTED `1d lightgbm v32` at −8.9%. A control
       that lets the deeper drawdown through is not measuring drawdown.
    3. **It mostly fired on UNRECORDED sizing, not on all-in sizing.** `_is_all_in` fails closed
       on a missing field and the discovery passes never stamp `sizing`, so the screen's real
       behaviour was "reject leveraged cells whose sizing field was never written" — a
       data-completeness artifact wearing the costume of a risk control.

    This repo had already diagnosed the same screen once (`.claude/rules/verify-and-judge-not-quote.md`
    records the all-in ban being quoted to unpublish 13 prod backtests, where "the ban was a PROXY
    for a defect the honest-MTM engine had already fixed"). It was re-committed anyway, by quoting
    the rule instead of running the corpus. The honest MTM drawdown IS the defect's real fix, and
    it is already wired: a leveraged all-in book that blows up now shows it as −100% MTM DD and
    dies on `mtm_drawdown_wipe`, which is a ruin screen and stays a kill.

    What replaces it is DISCLOSURE, not permissiveness: the sizing and the drawdown travel with
    the number so a reader can never see "$20,168, 3.35x B&H" without also seeing "all-in, −74%".
    """
    if _liquidation_count(cell) > 0:
        return EXCLUDED_LIQUIDATED
    if cell.get("account_bankrupt"):
        return EXCLUDED_BANKRUPT
    if _cell_drawdown_fraction(cell) <= DRAWDOWN_WIPE_THRESHOLD:
        return EXCLUDED_DRAWDOWN_WIPE
    return None


def headline_disclosures(cell: Mapping[str, Any]) -> tuple[str, ...]:
    """Risk facts that MUST be published beside this cell's money, in reading order.

    A disclosure never disqualifies — it makes the number honest. Empty means the cell carries no
    risk caveat beyond its own drawdown.
    """
    if _is_all_in(cell) and _is_leveraged(cell):
        return (DISCLOSURE_ALL_IN_LEVERAGED,)
    return ()


def is_ruin_reason(reason: str | None) -> bool:
    """True when `reason` describes an account the user actually LOST.

    The predicate a verdict must satisfy before it may be called a KILL. Guards the recurring
    failure this module exists to stop: reporting a profitable, ruin-clean, B&H-beating book as
    dead because of a label that is not about losing money.
    """
    return reason in RUIN_REASONS


def capital_is_ruined(cell: Mapping[str, Any]) -> bool:
    """Did this cell LOSE the account? One name for a question asked at five call sites.

    `is_ruin_reason(headline_exclusion_reason(cell))` was composed by hand in `loop_contract`,
    `gen_money_ledger` (twice), `check_discarded_money_makers` and `capital_cert_promote`. Each
    asks the identical question and each had to remember BOTH halves.

    Forgetting the second half is not hypothetical: `certify_return_book_lanes`'s docstring records
    **317 of 323** lane certs naming a `max_clean_leverage_survived` whose lane had LOST money,
    because ruin was asked with the wrong screen. A predicate the callers share cannot be
    half-remembered.

    Both parts stay public — a caller that needs the REASON string still wants
    `headline_exclusion_reason`, and `gen_money_ledger` prints it.

    THE CONTRADICTION ESCAPE LIVES HERE, NOT IN ONE CALLER (added 2026-08-25). The original
    version of this predicate was a bare `is_ruin_reason(headline_exclusion_reason(cell))`, while
    `gate._capital_cell_is_ruined` applied a further screen: a `mtm_drawdown_wipe` that the cell's
    OWN final capital disproves is not ruin. That left TWO policies for one question — the exact
    cost this docstring warns about — and they disagreed.

    MEASURED over 2,400 corpus artifacts (968,731 fully-shaped capital cells): the two answered
    differently on **269** cells. Every one had `liquidation_exits == 0`, reason
    `mtm_drawdown_wipe`, and a final capital ABOVE its start — lanes perp_3x/perp_5x over 89-239
    trades, e.g. $10,000 -> $60,091.75 at `max_drawdown = -1.0`. Cause is the pre-2026-08-12
    multi-position marking bug documented on `drawdown_contradicts_capital`: a hedged book marked
    each position at its own worst intrabar extreme, so it could measure -100% having lost nothing.

    The gate's answer is the correct one and is now the only one. Calling those 269 ruined is a
    false KILL of money-makers, and `b6d47ded2` had wired book RANKING onto this predicate.
    """
    reason = headline_exclusion_reason(cell)
    if not is_ruin_reason(reason):
        return False

    # ONLY the drawdown wipe is escapable, because it is the only reason that is an INFERENCE from
    # a number. A liquidation COUNT and `account_bankrupt` are records of what happened and stay
    # ruin whatever the final capital says — pinned by
    # `test_a_real_liquidation_still_kills_even_when_the_book_finished_up`.
    if reason != EXCLUDED_DRAWDOWN_WIPE:
        return True

    return not drawdown_contradicts_capital(cell)


def capital_cell_is_rankable(cell: Mapping[str, Any]) -> bool:
    """May this cell be RANKED (best lane, headline, published multiple)?

    NOT the same question as `capital_is_ruined`, and conflating them cost a real defect on
    2026-08-25. Ruin asks "did this lose the account". Rankable asks "do I trust this cell's
    numbers enough to put it in front of a user".

    A cell whose `max_drawdown` its own final capital DISPROVES fails the second while passing the
    first. `capital_is_ruined` must clear it — calling it ruined false-KILLs 269 measured corpus
    cells (all `liquidation_exits == 0`, lanes perp_3x/perp_5x, e.g. $10,000 -> $60,091.75). But
    it must not then WIN anything either: its drawdown is known-broken, so a ranking built on it
    is built on a number nobody can defend.

    That is the trap `test_a_fully_wiped_lane_is_excluded` caught. Its fixture — `-1.0` drawdown
    beside $99,000 from $10,000 — is accidentally a contradiction cell, and clearing ruin alone
    would have promoted it to richest-clean-lane. `1d lightgbm v42` is the shipped precedent for
    what that costs: a cell that took the account to ~zero, printed as the corpus's TOP performer.

    Untrustworthy is a THIRD state. It is not ruin and it is not clean.
    """
    if capital_is_ruined(cell):
        return False
    return not drawdown_contradicts_capital(cell)


def headline_eligible(cell: Mapping[str, Any]) -> bool:
    """True when this cell may be surfaced as a best / published as an edge."""
    return headline_exclusion_reason(cell) is None


def headline_survivors(cells: Iterable[_CellT]) -> list[_CellT]:
    """The publishable subset, order preserved.

    Generic over the cell type: it only READS each cell and returns the same objects. The engine
    passes ``Mapping`` rows from ``valid_grid_cells``; a ``list[dict]`` parameter refused them.

    An empty result is the honest answer to a grid of ruin cells — never fall back to the
    least-bad liquidating cell.
    """
    return [cell for cell in cells if headline_eligible(cell)]


logger = logging.getLogger(__name__)


def headline_pool(*passes: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Every cell a cert run computed, unioned — the ONLY pool a headline may be ranked from.

    A cert makes several passes: a bounded combo search (~25-300 cells) plus discovery passes over
    exits, holds, confidences, sizings and DCA depths (thousands of cells, same engine, same
    window). Ranking only the combo pass understates the run by orders of magnitude, because the
    discovery passes routinely contain the real best cell.

    That is not hypothetical. On 2026-08-05 the deployed model's out-of-sample cert published
    "$10,497 -- fails beats-B&H ($10,613)" from 25 combo cells while 3,106 liquidation-clean cells
    in the SAME artifact peaked at $99,136, 9.3x buy-and-hold. All 14 artifacts on disk were
    understated the same way, and one model (1d lightgbm v32) was KILLED on a headline of "zero
    valid cells" when its OOS run held 4,123 survivors beating B&H 2x.

    Unioning costs nothing -- the cells are already computed -- and makes "best" mean best OVERALL.
    Non-mappings are dropped rather than raising: a cert must never die on one malformed row.
    """
    return [dict(cell) for cells in passes for cell in cells or () if isinstance(cell, Mapping)]


#: Why a headline pool yielded nothing publishable. THREE different facts that an empty list
#: spells identically, which is the whole reason these exist.
EMPTY_NO_CELLS: Final = "no_cells_computed"
EMPTY_ALL_THIN: Final = "all_cells_thin"
EMPTY_ALL_RUINED: Final = "all_cells_ruined"


def headline_empty_reason(
    cells: Iterable[Mapping[str, Any]] | None,
    *,
    min_trades: int = MIN_TRADES_FOR_SHARPE,
) -> str | None:
    """Why no cell here may be published, or ``None`` when at least one may.

    An empty headline is not self-explanatory, and the three states it can mean call for
    opposite responses:

    * ``EMPTY_NO_CELLS`` -- the run computed nothing. An INFRASTRUCTURE defect: go fix the run.
    * ``EMPTY_ALL_THIN`` -- cells exist, none clears the turnover floor. A statement about the
      BOOK: it does not trade often enough to be measured, so neither a promotion nor a kill is
      available. Measured 2026-09-02 on the deployed 1h book: 9,723 cells, every one a single
      trade, unresponsive to all 81 exits and every confidence threshold.
    * ``EMPTY_ALL_RUINED`` -- cells clear the floor and every one lost the account. A KILL, and
      the only one of the three that is.

    Thin is reported BEFORE ruin: with too few trades the liquidation count is not measured
    either, so calling a one-trade liquidation "this book loses accounts" over-claims from a
    single sample.

    Complements ``empty_grid_refusal`` (edge_inventory_capital_selection), which covers the
    other cause of an empty headline -- every per-cell backtest THREW. That one is about the
    run; this one is about the cells the run produced. Non-mappings are dropped rather than
    raising, matching `headline_pool`: a cert must never die on one malformed row.
    """
    rows = [cell for cell in cells or () if isinstance(cell, Mapping)]
    if not rows:
        return EMPTY_NO_CELLS

    measurable = [cell for cell in rows if not is_thin_sample(cell, min_trades=min_trades)]
    if not measurable:
        return EMPTY_ALL_THIN

    if any(headline_eligible(cell) for cell in measurable):
        return None
    return EMPTY_ALL_RUINED


#: Turnover floor for SELECTING a cell to pre-commit to. Half the significance bar, because the
#: select window is roughly half the out-of-sample slice: a cell trading this often on that half
#: should still trade enough on a similar-length confirm window to be measurable.
MIN_SELECT_TRADES: Final = MIN_TRADES_FOR_SHARPE // 2


def meets_turnover_floor(cell: Mapping[str, Any], *, min_trades: int = MIN_SELECT_TRADES) -> bool:
    """Does this cell trade often enough to be a BOOK rather than a lucky streak?

    Ranking a select window by final ``$`` alone re-selects low-turnover cells that caught one move
    and then sat still — they look spectacular and cannot be confirmed. Measured 2026-08-05: prod
    v2's best-by-money select cell traded **9** times (hold30, spot) and yielded a 2-trade confirm;
    v33's traded **16** (hold24) and yielded 25. Both then "beat B&H" on the confirm window while
    LOSING 12% and 24% of capital.

    With the floor applied the selection becomes a real book — prod v2 → 262 trades (hold3,
    perp_5x), v33 → 94 — at a cost of 5-14% of the SELECT window's money, which is discarded by
    construction. So the floor is free. v11 already selected a 431-trade cell and is unchanged.

    Fails closed on an unknown count, like every other predicate here.
    """
    raw = cell.get("num_trades")
    if raw is None:
        return False
    try:
        return int(raw) >= int(min_trades)
    except TypeError, ValueError:
        return False


def is_profitable(cell: Mapping[str, Any], *, initial_capital: float) -> bool:
    """Did this book actually MAKE money — independent of how the benchmark did?

    "Beats B&H" is satisfiable by losing less. v33's select-confirm cell ended at $7,551 from
    $10,000 — down 24% — against a benchmark that fell to $5,821, and was duly reported as
    "BEATS B&H". In a bear window the ratio flatters a book that cost the user a quarter of their
    capital, so profitability has to be stated separately and never inferred from the comparison.

    Strictly greater than the starting capital: flat after fees and slippage is not a win. Fails
    closed on a missing final, consistent with the sizing and leverage predicates.
    """
    raw = cell.get("final_capital")
    if raw is None:
        return False
    try:
        return float(raw) > float(initial_capital)
    except TypeError, ValueError:
        return False


def drawdown_contradicts_capital(cell: Mapping[str, Any]) -> bool:
    """True when a cell records a TOTAL drawdown that its own final capital disproves.

    An account marked to −100% is dead. It cannot then finish ABOVE where it started, and the engine
    already flags `fantasy_post_ruin_trades` for a book that keeps trading after ruin. So a cell with
    all of: `max_drawdown <= -1.0`, `final_capital > initial_capital`, `account_bankrupt` false, and
    no post-ruin trades — is recording two facts that cannot both hold. WHICH one is wrong is NOT
    decided here and must be measured per cell: C-0 (2026-09-15) found prod v2 truly ruined (the
    capital was the lie) while v42 and v12 kept realized books ending +30%/+34% under a -100% intrabar
    mark; whether that mark is a real wipe is unmeasured (C-0x; `by_year` is closed-trade, not MTM).
    Mixed-direction overstatement is pinned by `TestMixedDirectionBooksAreNotOverstated`.

    MEASURED 2026-08-16: 3 of the 13 pre-commitment confirms are in exactly that state. `1d_42` is
    the sharpest — −100% drawdown beside **$12,815 from $10,000**, zero liquidations — and that one
    figure has now produced a wrong verdict in BOTH directions: killed on it once (retracted as
    unverifiable), then published as a 1.79× passer, then retracted as ruin, then restored. A number
    a reader can take either way is worse than a missing one, because each reader picks.

    This answers ONLY "is this pair impossible". A missing drawdown is a different defect and is not
    flagged here.
    """
    dd = cell.get("max_drawdown")
    final = cell.get("final_capital")
    initial = cell.get("initial_capital")
    if not isinstance(dd, int | float) or not isinstance(final, int | float) or not isinstance(initial, int | float):
        return False
    if dd > -1.0:
        return False
    if cell.get("account_bankrupt") or int(cell.get("fantasy_post_ruin_trades") or 0) > 0:
        return False  # the wipe was real; the drawdown is telling the truth
    return final > initial


def headline_trial_sharpes(
    cells: Iterable[Mapping[str, Any]],
    *,
    min_trades: int = MIN_TRADES_FOR_SHARPE,
) -> list[float]:
    """Sharpes of the cells the headline was actually SELECTED FROM — the deflation population.

    A combinatorial cert evaluates thousands of lever combinations and publishes the best. That is
    a best-of-N selection, so the winner's Sharpe is inflated by construction, and Deflated Sharpe
    only corrects it when handed the REAL trial count and dispersion.

    The population is the publishable, measurable candidates — not the raw pool. Ruin cells carry
    meaningless Sharpes (a -46,327 was found on disk 2026-08-05) that would balloon the dispersion
    and thereby WEAKEN the deflation, which is backwards: garbage trials must not make a headline
    look more significant.

    Measured on the corpus the day this was added, every 1d leader failed once deflated honestly:
    v33 SR 1.445 from 1,481 candidates, prod v2 SR 2.432 from 1,925, v11 SR 1.317 from 2,363 — all
    DSR 0.0, where ~SR 5 is what that trial count demands. The money is real; the SELECTION is not
    yet shown to be skill.
    """
    return [
        float(cell["sharpe_ratio"])
        for cell in headline_survivors([dict(c) for c in cells])
        if cell.get("sharpe_ratio") is not None and not is_thin_sample(cell, min_trades=min_trades)
    ]


__all__ = [
    "ALL_IN_SIZING",
    "CELL_FIELD_ACCOUNT_LIQUIDATED",
    "CELL_FIELD_LIQUIDATION_EXITS",
    "CELL_FIELD_MAX_DRAWDOWN",
    "CELL_FIELD_MAX_DRAWDOWN_PCT",
    "DISCLOSURE_ALL_IN_LEVERAGED",
    "DRAWDOWN_WIPE_THRESHOLD",
    "EMPTY_ALL_RUINED",
    "EMPTY_ALL_THIN",
    "EMPTY_NO_CELLS",
    "EXCLUDED_ALL_IN_LEVERAGED",
    "EXCLUDED_BANKRUPT",
    "EXCLUDED_DRAWDOWN_WIPE",
    "EXCLUDED_LIQUIDATED",
    "RUIN_REASONS",
    "capital_cell_is_rankable",
    "drawdown_contradicts_capital",
    "headline_disclosures",
    "headline_eligible",
    "headline_empty_reason",
    "headline_exclusion_reason",
    "headline_pool",
    "headline_survivors",
    "headline_trial_sharpes",
    "is_ruin_reason",
]
