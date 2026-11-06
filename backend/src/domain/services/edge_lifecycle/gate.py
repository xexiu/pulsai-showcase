"""Canonical edge-hunt gate — the single source of truth for verdict / promote / retention.

Reconciles the ~6 copy-pasted ``verdict(ic, sr, dsr, fold_stab)`` helpers scattered across
``src/research/edge_hunt/*`` (which had drifted: EDGE dsr>0.90 vs >=0.80, CANDIDATE dsr>0.75
vs >=0.50). Those scripts should import ``research_verdict`` from here.

Lifecycle (owner spec 2026-07-17):
  RESEARCH -> PoC -> full grid -> validate -> ``research_verdict``
    EDGE      : auto-promote to prod IFF the capital backtest passes (2017->today, spot/lev/exit,
                init 10k -> final > init). Forward-soak is a red/green LABEL only, NOT a hard gate
                (see forward_soak_badge.py). If capital fails -> hold as CANDIDATE.
    CANDIDATE : keep + optional R2; show on full chart; NO prod promote (force/push to become EDGE).
    SCOUT     : keep (force/push toward CANDIDATE); if judged not worth pushing -> NICE_TO_HAVE or KILL.
    NICE_TO_HAVE : keep file + R2 ONLY if the capital backtest passes 2017->today, else KILL.
    NULL/KILL : archive (reversible), do not retain in the live registry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

from src.domain.services.edge_lifecycle import cell_measurability as _cell_measurability

if TYPE_CHECKING:
    from collections.abc import Mapping

# Re-exported, not defined: the flat thin-sample floor lives beside the MinTRL derivation it backs up.
MIN_TRADES_FOR_SHARPE: Final = _cell_measurability.MIN_TRADES_FOR_SHARPE

# ── Verdict tiers (SoT strings; match edge_hunt_model_staging where they overlap) ──────────
EDGE: Final = "edge"
CANDIDATE: Final = "candidate"
SCOUT: Final = "scout"
NICE_TO_HAVE: Final = "nice_to_have"
NULL: Final = "null"
KILL: Final = "kill"

Verdict = Literal["edge", "candidate", "scout", "null"]
PromoteDecision = Literal["auto_promote_edge", "hold_candidate", "no_promote"]
RetentionDecision = Literal["keep_and_r2", "keep_local", "archive"]
EscalationDecision = Literal["promote_edge", "keep_candidate", "nice_to_have", "trails_bh", "unmeasured", "kill"]

PROMOTE_AUTO_EDGE: Final = "auto_promote_edge"
PROMOTE_HOLD_CANDIDATE: Final = "hold_candidate"
PROMOTE_NONE: Final = "no_promote"

ESCALATION_PROMOTE_EDGE: Final = "promote_edge"
ESCALATION_KEEP_CANDIDATE: Final = "keep_candidate"
ESCALATION_NICE_TO_HAVE: Final = "nice_to_have"
ESCALATION_KILL: Final = "kill"
#: The account is ALIVE but trails same-window B&H (or carries no lane table): kept, not staged, never killed.
ESCALATION_TRAILS_BH: Final = "trails_bh"
#: The money could not be priced (no lane table, or impossible money from a leak): kept, not staged, never killed.
ESCALATION_UNMEASURED: Final = "unmeasured"

# ── Gate lanes (SoT) ──────────────────────────────────────────────────────────
# IC lane: directional forecasters (rank-IC required for EDGE).
# Book lane: execution books (VRP / vt-17 / XS …) — SR/DSR/fold_stab only; IC optional/ignored.
GATE_LANE_IC: Final = "ic"
GATE_LANE_BOOK: Final = "book"
GateLane = Literal["ic", "book"]

# ── Canonical thresholds (reconciled to the stricter calculate_all_zoo rule) ───────────────
EDGE_IC_MIN: Final = 0.02
EDGE_SR_MIN: Final = 0.5
EDGE_DSR_MIN: Final = 0.90
EDGE_FOLD_STAB_MIN: Final = 0.6

CANDIDATE_IC_MIN: Final = 0.01
CANDIDATE_SR_MIN: Final = 0.3
CANDIDATE_DSR_MIN: Final = 0.75
CANDIDATE_FOLD_STAB_MIN: Final = 0.5

SCOUT_IC_MIN: Final = 0.0
SCOUT_SR_MIN: Final = 0.0


# ── Plausibility floor (added 2026-07-31 after a corpus audit) ────────────────────────────
# The gate used to accept whatever numbers a research script handed it, and 40 cells reached
# EDGE on metrics that cannot physically occur — e.g. ``vrpband_l0__sa_4h`` graded ic=1.0,
# sr=62.695, final_capital=$3.9e39 from $10k, because a VRP *level* series was passed where
# per-bar net RETURNS are expected and ``fold_ics`` was literally ``sign(mean)`` (so the IC term
# auto-passed at +/-1). Calibration: the corpus's best genuine books run ann-SR 1.3 (vt-17) to
# 2.9 (VRP dvol_mom); published practice treats a backtest Sharpe above ~3 as a methodology-error
# signal, so 5.0 is already generous. A rank-IC of ~1.0 is definitionally degenerate — a real
# crypto XS rank-IC lives at 0.02-0.07.
SR_IMPLAUSIBLE_ABS: Final = 5.0
IC_DEGENERATE_ABS: Final = 0.95
#: Wealth multiple above which a compounding path is not a result, it is a bug. This is a PHYSICAL
#: POSSIBILITY floor, not a quality bar — it must not reject a legitimately spectacular book.
#:
#: MEASURED 2026-08-13 over 615 hunt cells carrying a capital pair, before moving it:
#:     1e6 (previous)  rejects   5 (0.8%)   waved through 53,299x and 40,568x
#:     1e4 (this)      rejects  12 (2.0%)
#:     1e3             rejects  32 (5.2%)   starts catching plausible high-leverage books
#: The top cell read 1.06e151x — a diverged path, not a return.
#:
#: The corpus window is ~5.6 years, so 1e4 is 393%/yr sustained. Nothing real compounds like that,
#: while 98% of cells are still left to be judged on their merits.
WEALTH_IMPLAUSIBLE_MULT: Final = 1e4


@dataclass(frozen=True)
class GateMetrics:
    """Honest-gate inputs for one candidate (all from purged walk-forward OOS)."""

    ic: float
    sr: float
    dsr: float
    fold_stab: float


def _verdict_ladder(m: GateMetrics, *, ic_gate: bool) -> Verdict:
    """The ONE EDGE / CANDIDATE / SCOUT / NULL ladder. The lane differs only by whether IC gates.

    These were two functions with byte-identical structure — `find_clones` scores them 1.00 — whose
    only real difference is that the book lane ignores IC. `research_verdict_book`'s own docstring
    said *"Same SR/DSR/fold thresholds as the IC lane so EDGE bar stays honest"*, which is a
    keep-in-sync comment, and `.claude/rules/` records what those always do: drift. A threshold
    edit had to be made in two places or the two lanes would silently grade differently.

    ``abs(ic)`` because a consistently sign-flipped-but-real signal still scores; the leaderboards
    sign-correct downstream.

    AN UNMEASURED STATISTIC IS NOT A FAILED ONE. Every comparison against NaN is False, so a
    cell carrying no IC used to fail EVERY rung at once and land on "null" -> kill. NaN does
    not fail one threshold; it fails all of them, silently, and the artifact still printed a
    number-shaped ``0.0``.

    MEASURED 2026-09-20 over 7,617 hunt cells: 147 graded on ``gate_lane='ic'`` with no IC,
    124 killed, **100 of those had a surviving, growing account and 21 beat buy-and-hold** --
    including vt-17 cells finishing at $53.2M / $64.3M / $29.4M and every ``ema200_bos_fvg``
    timeframe (4h: 5.6 years, spot $21,760 with zero liquidations, perp_3x $77,426).

    So NaN is routed the way this function ALREADY routed a NaN DSR: **unknown may not buy the
    top tier, but it must not block the middle one.** EDGE auto-promotes to production, so an
    unmeasured term can never earn it (``nan > MIN`` stays False there by construction);
    CANDIDATE and SCOUT treat it as unknown. A MEASURED bad value keeps its full blocking
    power -- 0.001 is bad, NaN is absent, and the two are now different facts.

    ``fold_stab`` gets the same treatment for the same reason: with zero walk-forward folds it
    is 0/0, i.e. undefined. Reporting 0.0 asserts "no fold was positive", which is a different
    and false claim -- and it is the claim that blocked CANDIDATE for every rule-based book,
    none of which trains weights or runs folds at all.
    """
    ic = abs(m.ic)
    ic_unknown = math.isnan(ic)
    folds_unknown = math.isnan(m.fold_stab)
    dsr_ok_edge = m.dsr >= EDGE_DSR_MIN
    # A lane without an IC gate passes the IC test vacuously — never by faking a value.
    ic_edge = ic > EDGE_IC_MIN if ic_gate else True
    ic_cand = (ic > CANDIDATE_IC_MIN or ic_unknown) if ic_gate else True
    ic_scout = (ic > SCOUT_IC_MIN or ic_unknown) if ic_gate else True
    folds_ok_edge = m.fold_stab >= EDGE_FOLD_STAB_MIN
    folds_ok_cand = m.fold_stab >= CANDIDATE_FOLD_STAB_MIN or folds_unknown

    if ic_edge and m.sr > EDGE_SR_MIN and dsr_ok_edge and folds_ok_edge:
        return "edge"
    # DSR does not gate CANDIDATE (LENIENT-2, owner 2026-10-04: research/money gates must not be strict).
    # The hunt cell discloses it instead (`dsr_below_candidate_bar`, stamped in loop_contract.finalize_dsr).
    # EDGE keeps the DSR bar above: it auto-promotes to production.
    if ic_cand and m.sr > CANDIDATE_SR_MIN and folds_ok_cand:
        return "candidate"
    if ic_scout and m.sr > SCOUT_SR_MIN:
        return "scout"
    return "null"


def research_verdict(m: GateMetrics) -> Verdict:
    """IC lane / research tier: rank-IC gates every rung alongside SR / DSR / fold stability."""
    return _verdict_ladder(m, ic_gate=True)


def research_verdict_book(m: GateMetrics) -> Verdict:
    """Execution-book lane: SR / DSR / fold_stab only — IC is ignored (never fake IC).

    ``fold_stab`` MUST be the fraction of OOS folds with **positive fold Sharpe**, not rank-IC.
    """
    return _verdict_ladder(m, ic_gate=False)


#: Verdicts that outrank the suspect-IC cap, so only these get downgraded by it.
_ABOVE_SUSPECT_IC_CAP: Final[frozenset[str]] = frozenset({"edge", "candidate"})

#: A forward-PRICE rank-IC in crypto lives at 0.02-0.07 (this corpus's own measured ceiling).
#: An order of magnitude above that is not a price IC — it is an IC against a different, far more
#: predictable target (funding-predicting-funding, say, which is trivially persistent).
#:
#: SoT lives HERE, in the domain, because both the emitter and the gate need it and the runtime
#: may not import from ``src/research``. ``loop_contract`` imports this symbol.
PRICE_IC_CEILING: Final = 0.30

#: Best verdict an undeclared suspect IC may earn. Not "null": the cell is not proven fake, only
#: proven un-gradeable on IC, and the emitter can fix that by declaring its lane.
SUSPECT_IC_MAX_VERDICT: Final[Verdict] = "scout"


def ic_is_suspect_for_lane(ic: float, *, gate_lane: str) -> bool:
    """True when this IC is too large to be the forward-PRICE IC its lane claims.

    Mirrors ``loop_contract._flag_emission_sanity``, which stamps ``ic_suspect`` on the cell with
    exactly this test. The book lane is exempt: it ignores IC entirely, so no IC can flatter it.
    """
    return gate_lane != GATE_LANE_BOOK and abs(ic) > PRICE_IC_CEILING


def select_research_verdict(m: GateMetrics, *, gate_lane: str = GATE_LANE_IC) -> Verdict:
    """Route to IC or book lane verdict. Unknown lane → IC (fail-closed to stricter gate).

    An IC above :data:`PRICE_IC_CEILING` in the IC lane is capped at
    :data:`SUSPECT_IC_MAX_VERDICT`. MEASURED 2026-08-21: 11 of 11 promoted books in the corpus
    were `ic_suspect: True` with `gate_lane: "ic"` — every promotion was graded over the
    pipeline's own leak warning, because that warning was written to the artifact and never read
    back. ``ic > EDGE_IC_MIN`` is trivially passed by an IC measured against something else.

    This does NOT silently re-lane the cell — ``_flag_emission_sanity`` chose "flagged, not
    re-laned: the emitter must declare its lane", and that stands. It declines to GRADE what the
    emitter has not declared. Declaring ``gate_lane='book'`` restores the full verdict, so the
    emitter keeps the fix in its own hands.
    """
    if gate_lane == GATE_LANE_BOOK:
        return research_verdict_book(m)

    verdict = research_verdict(m)
    if ic_is_suspect_for_lane(m.ic, gate_lane=gate_lane) and verdict in _ABOVE_SUSPECT_IC_CAP:
        return SUSPECT_IC_MAX_VERDICT
    return verdict


def implausible_metrics(
    m: GateMetrics,
    *,
    initial_capital: float | None = None,
    final_capital: float | None = None,
) -> list[str]:
    """Reasons these numbers cannot describe a real book — empty list means plausible.

    This is a *physical possibility* check, not a quality bar: it catches a broken harness
    (level series fed as returns, a sign proxy fed as an IC, a compounding path that exploded),
    NOT a merely-optimistic result. NaN is "unknown", never "implausible", so a legitimately
    unmeasured field cannot trip the guard.
    """
    reasons: list[str] = []
    if math.isfinite(m.sr) and abs(m.sr) > SR_IMPLAUSIBLE_ABS:
        reasons.append(f"|sr|={abs(m.sr):.2f} exceeds {SR_IMPLAUSIBLE_ABS} (no real book clears this)")
    if math.isfinite(m.ic) and abs(m.ic) >= IC_DEGENERATE_ABS:
        reasons.append(f"|ic|={abs(m.ic):.3f} is degenerate (>={IC_DEGENERATE_ABS}: a proxy, not a rank-IC)")
    if initial_capital is not None and final_capital is not None and initial_capital > 0:
        if not math.isfinite(final_capital):
            reasons.append("wealth is non-finite (compounding path diverged)")
        elif final_capital / initial_capital > WEALTH_IMPLAUSIBLE_MULT:
            reasons.append(f"wealth={final_capital / initial_capital:.2e}x exceeds {WEALTH_IMPLAUSIBLE_MULT:.0e}x")
    return reasons


def guarded_research_verdict(
    m: GateMetrics,
    *,
    gate_lane: str = GATE_LANE_IC,
    initial_capital: float | None = None,
    final_capital: float | None = None,
    capital_cell: Mapping[str, Any] | None = None,
) -> Verdict:
    """``select_research_verdict`` with TWO floors applied first.

    Prefer this over the raw verdict helpers anywhere a research script's self-reported metrics
    reach the gate. Pair it with ``implausible_metrics`` when you need the reasons to log.

    The floors answer different questions and both must be asked:

    * ``implausible_metrics`` — are these NUMBERS physically possible? (|SR|>5, |IC|>=0.95, a
      wealth multiple above 1e4).
    * ``capital_cell`` — did the ACCOUNT SURVIVE? A cell that liquidated, went bankrupt or was
      wiped mark-to-market cannot support a money verdict however good its metrics look.

    THE SECOND FLOOR, MEASURED 2026-08-21. ``orchestrator.evaluate`` already builds the capital
    dict — it carries ``max_drawdown``, ``liquidation_exits`` and ``account_bankrupt`` — and
    passed only initial/final/trades here. So the tier was decided without ever being shown
    whether the account survived, and **38 of 221 tiered hunt books hold a money tier on a cell
    the SoT calls ruined**, including one at ``nice_to_have`` with $10,000 -> $45.72 and a -100%
    mark-to-market drawdown. Re-running those books could not have re-graded them, because the
    screen that refuses them was not on the path.

    That is the same shape as the 2026-08-15 finding, when this very function was unreachable
    from the hunt loop. A screen exists; the path does not reach it.

    RUIN IS THE SoT'S CALL, NOT A THRESHOLD HERE: ``is_ruin_reason(headline_exclusion_reason())``
    is the single answer to "is this ruin", shared with ``best_clean_lane_wealth`` and the corpus
    ratchet. Deriving a drawdown number locally is how a corpus ends up with contradictory tiers.

    NOT A DRAWDOWN FLOOR. Deep drawdown stays a DISCLOSURE and the risk is the user's to take — a
    book at -94.7% ending at $1,073,745 keeps its verdict. Only a DEAD account downgrades one.

    ``capital_cell`` is optional and absence is never evidence of ruin: every existing call site
    omits it and behaves exactly as before.
    """
    if implausible_metrics(
        m,
        initial_capital=initial_capital,
        final_capital=final_capital,
    ):
        return "null"
    if capital_cell and _capital_cell_is_ruined(capital_cell):
        return "null"
    return select_research_verdict(m, gate_lane=gate_lane)


def _capital_cell_is_ruined(capital_cell: Mapping[str, Any]) -> bool:
    """Did this cell ruin the account? Delegates to the SoT screen, lazily imported.

    Lazy because ``capital_cert_headline`` sits beside this module in the same package, and a
    top-level import would couple the gate's import graph to the headline machinery for a check
    most callers never reach.

    FAILS OPEN: an unreadable cell is not evidence of ruin, and a broken screen must never fail a
    book closed.

    THE POLICY MOVED, 2026-08-25. This function used to compose the screen by hand AND carry the
    drawdown-contradiction escape that ``capital_is_ruined`` lacked, so the two disagreed on 269
    real corpus cells (all `liquidation_exits == 0`, reason `mtm_drawdown_wipe`, finishing above
    their start). The escape now lives in the SoT, where every caller gets it; this is a thin
    delegation so the two can never drift again.
    """
    try:
        from src.domain.services.edge_lifecycle.capital_cert_headline import capital_is_ruined

        return capital_is_ruined(capital_cell)
    except ImportError, AttributeError, KeyError, TypeError, ValueError:
        # Fail OPEN on a malformed capital block: absence of evidence is never evidence of ruin.
        return False


def capital_backtest_passes(initial_capital: float, final_capital: float) -> bool:
    """Smoke / leaf capital gate: final stake must strictly exceed initial.

    For EDGE **auto-promote** on CryptoBT leaves, prefer
    ``resolve_promote_capital_pass`` / ``capital_certification`` (spot grew + 3x not wiped).
    This helper remains the compound-smoke and inapplicable-fallback predicate.
    """
    if not math.isfinite(initial_capital) or not math.isfinite(final_capital) or initial_capital <= 0:
        return False
    return final_capital > initial_capital


def promote_decision(verdict: str, *, capital_pass: bool) -> PromoteDecision:
    """Whether a verdict auto-promotes to prod. EDGE promotes IFF the capital backtest passes."""
    if verdict == EDGE and capital_pass:
        return PROMOTE_AUTO_EDGE
    if verdict == EDGE and not capital_pass:
        return PROMOTE_HOLD_CANDIDATE  # EDGE metrics but capital backtest fails -> hold, do not ship
    return PROMOTE_NONE


def retention_decision(staging: str, *, capital_pass: bool) -> RetentionDecision:
    """Artifact retention. NICE_TO_HAVE survives (keep + R2) ONLY if the capital backtest passes.

    EDGE always R2 when capital passes (else keep_local). CANDIDATE always ``keep_and_r2``
    (FULL-chart display ≠ prod promote — owner LE-D alignment 2026-07-21 / USING_THE_LOOP.md).
    SCOUT retained locally (still being pushed toward CANDIDATE). NULL/KILL -> archive
    (reversible, never hard-deleted here).
    """
    if staging == EDGE:
        return "keep_and_r2" if capital_pass else "keep_local"
    if staging == CANDIDATE:
        return "keep_and_r2"
    if staging == SCOUT:
        return "keep_local"
    if staging == NICE_TO_HAVE:
        return "keep_and_r2" if capital_pass else "archive"
    return "archive"  # null / kill / unknown
