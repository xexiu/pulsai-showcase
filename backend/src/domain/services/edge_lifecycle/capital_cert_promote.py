"""Staged CryptoBT capital certification for EDGE promote (not every-loop smoke).

Smoke ``capital_backtest`` stays compound equity for NULL/SCOUT filtering.
EDGE auto-promote requires a ``capital_certification`` block:
  * ``certified`` / ``failed`` with ``capital_modes`` → spot grew AND perp_3x not wiped
  * ``inapplicable`` → fall back to smoke compound (VRP / XS / sizing / funding leaves)
  * absent / ``pending_cryptobacktester`` on EDGE → do not auto-promote (hold_candidate)
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from typing import Any, Final

from src.domain.services.edge_lifecycle.capital_cert_lanes import (
    _SPOT_LANE,
    MAX_DD_FLOOR,
    _lane_final,
    _lane_initial,
    _lane_is_bankrupt,
    _lane_max_drawdown,
    _spot_bh_final,
    capital_cert_lanes,
)
from src.domain.services.edge_lifecycle.capital_cert_levered import (
    _levered_return_supports_production_promote,
    publishable_levered_lanes,
)
from src.domain.services.edge_lifecycle.capital_cert_routes import _leverage_route_passes, _spot_route_passes
from src.domain.services.edge_lifecycle.capital_cert_window_read import (
    CERT_HEADLINE_DSR_KEY,
    CERT_HEADLINE_DSR_PRESENT_KEY,
    CERT_WINDOW_IN_SAMPLE_KEY,
    CERT_WINDOW_KEY,
    DISCLOSURE_HEADLINE_DSR_MISSING,
    capital_cert_disclosures,
    capital_cert_headline_deflation_present,
    capital_cert_window_flag,
    capital_cert_window_role,
)

# Re-exported, not merely imported: `cert_window_role` now DEFINES this vocabulary, and every
# existing consumer imports it from here. Keeping the names importable from this module is what
# makes the move a relocation rather than a breaking change.
from src.domain.services.edge_lifecycle.cert_window_role import (
    CERT_WINDOW_ROLE_CONFIRM,
    CERT_WINDOW_ROLE_KEY,
    CERT_WINDOW_ROLE_SELECT,
    CERT_WINDOW_ROLES,
)
from src.domain.services.edge_lifecycle.gate import EDGE, capital_backtest_passes
from src.shared.constants.capital_cert_harness import CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK

logger = logging.getLogger(__name__)

CAPITAL_CERT_STATUS_CERTIFIED: Final = "certified"
CAPITAL_CERT_STATUS_FAILED: Final = "failed"
CAPITAL_CERT_STATUS_INAPPLICABLE: Final = "inapplicable"
CAPITAL_CERT_STATUS_PENDING: Final = "pending_cryptobacktester"


def cryptobt_capital_cert_passes(
    capital_certification: Mapping[str, Any],
    *,
    model_artifact_present: bool | None = None,
    window_is_in_sample: bool | None = None,
) -> bool:
    """True when the book makes money EITHER on spot OR at surviving leverage.

    ``model_artifact_present`` lets a caller declare whether the certified model still EXISTS. A
    cert whose ``model.joblib`` is gone cannot be re-verified, re-run or deployed, yet the JSON
    still carries lane money and a status and reads as authoritative — an unfalsifiable claim. 15
    of 26 local certs were in that state on 2026-08-04 (machine reset wiped the artifacts and R2
    does not hold them), and two of them fail the cert harness outright with FileNotFoundError.
    ``None`` means the caller did not check and preserves existing behaviour; resolving the path is
    the caller's job because this layer stays I/O-free (DDD_PATTERNS: domain = rules, no I/O).

    Two routes, per the ml-gate rule ("Verdict tier = best over {spot-honest-gate, beats-B&H at the
    max surviving leverage lane}"):

    1. **spot route** — spot grew and perp_3x is not wiped. This is the original behaviour.
    2. **leverage route** — spot may LOSE, provided a leverage lane is liquidation-clean, not
       bankrupt, and its final capital beats the SAME-WINDOW spot B&H final.

    Route 2 is why this function changed: it previously required ``capital_backtest_passes(init,
    spot_final)`` unconditionally, so a model that lost on spot could never be certified no matter
    how profitable perp was — the exact opposite of the rule, which states that a signal "marginal
    or even negative on SPOT but [compounding] profitably at leverage without liquidating IS a
    valid, promotable ML signal". A user trading the perp book was being denied a working model
    because the spot lane happened to be negative.

    Fails closed: with no same-window B&H reference there is nothing to beat, so the leverage route
    cannot be claimed and only the spot route can pass. ``account_bankrupt`` (fantasy post-ruin /
    wipe) fails even if a stale final_capital is still positive, and an 8x wipe alone does not fail
    the spot route.
    """
    if model_artifact_present is False:
        return False
    # A null headline DSR is disclosed (capital_cert_disclosures), never a veto: LENIENT-4, 2026-10-04,
    # released 9 of 192 certs. The money checks below still decide; ruin and in-sample still exclude.
    # DELIBERATELY NOT ALSO GATED ON THE DSR *VALUE* HERE. Written, measured, and reverted the
    # same hour (2026-08-15) — the record is kept because the reasoning is not obvious and the
    # mistake is easy to repeat.
    #
    # The idea looked airtight: `headline_deflated_sharpe` is computed, written to every cert, and
    # never read for its value, so a cert recording 0.0 promoted exactly like one recording 0.99.
    # Each cert even carries `"reason": "... headline is best-of-N — read
    # capital_x_exit.deflated_sharpe before citing it"`. Adding `value < 0.95 -> reject` refused 8
    # of the 10 certs that carry a DSR.
    #
    # It was WRONG, because the DSR and this predicate describe DIFFERENT CELLS:
    #
    #   `headline_deflated_sharpe` prices `capital_x_exit.overall_combo_best` — ONE cell chosen
    #       from ~6,000-20,000 combo cells, which is why it deflates to ~0.
    #   THIS function scores `capital_modes` — the seven PRE-SPECIFIED leverage lanes
    #       (spot/3x/4x/5x/6x/7x/8x). Choosing among 7 fixed lanes is not a best-of-6,000 search.
    #
    # Deflating a 7-lane result by a 6,000-cell trial count is wrong by ~three orders of
    # magnitude, and it costs real money: `1d gradient_boosting_clf/v10` carries
    # `headline_deflated_sharpe` 6.2e-38 while its `capital_modes.perp_3x` lane turned $10,000
    # into **$14,664 against a $6,797 buy-and-hold — 2.16x, with zero liquidations**. The gate
    # refused it on a statistic belonging to a different cell.
    #
    # The DSR is still the right question in the right place: WHERE THE COMBO HEADLINE IS CITED
    # (ledger, publish, tier copy), not where fixed lanes are scored. Same class of error as
    # pairing a thin `overall_combo_best` with a deflation population that excludes thin cells.
    # An IN-SAMPLE cert is not promotion evidence: a window spanning the model's own training period
    # measures fit, not edge. Measured on 2026-08-05 rather than assumed — the PRODUCTION model's
    # promotion evidence was a cert starting 7.75 years BEFORE its held-out boundary, and re-running
    # it on the unseen slice alone changed the answer materially ($148k in-sample vs $23.6k OOS
    # against a $10.6k benchmark). Same reasoning as ``model_artifact_present=False``: evidence that
    # cannot be falsified cannot promote.
    #
    # FAILS CLOSED on unknown since 2026-08-09. This used to read "``None`` deliberately PASSES:
    # 27 of 28 legacy certs never recorded their window, and blocking on unknown would invalidate
    # the whole corpus on a technicality rather than on a finding."
    #
    # That was true when written and the premise is checkable, so it was checked — TWICE, because
    # the first check measured the wrong corpus. Counting ``window_is_in_sample`` across the
    # ``full_report`` artifacts gives True 12 / False 18 / MISSING 0 and suggests the exemption is
    # now free to remove. But this predicate is handed the ``capital_certification.json`` SUMMARY,
    # and across all 42 of those on disk the flag is present **0 times**: the full report records
    # it and the summary drops it on the floor.
    #
    # So the exemption was load-bearing only because of a propagation gap.
    #
    # CORRECTED 2026-08-14. This paragraph used to credit a helper named ``stamp_cert_window_flag``
    # with "copying the flag down". THAT FUNCTION DOES NOT EXIST: a repo-wide search returns exactly
    # one hit — this comment citing it. Nobody wrote it, so an agent (me) read the comment, believed
    # the gate was a blanket refusal, and nearly published "nothing in the corpus can promote".
    #
    # What actually closes the gap needs no separate stamper: ``run_edge_capital_x_exit_grid`` writes
    # ``window_is_in_sample`` straight into the cert's ``window`` block at build time, and
    # ``capital_cert_window_flag`` above reads top level THEN that nested block. Measured over the 63
    # ``capital_certification.json`` on disk: nested False 31, True 6, absent 26 — so the gate is
    # armed and discriminating for 37 of them, not refusing everything.
    #
    # The 26 that still say nothing are the real remaining debt, and they fail closed on purpose.
    #
    # What it costs: 5 records flip pass -> fail until they carry the flag, including prod
    # ``btc_usdt_1d/gradient_boosting_clf/v2``. What it buys: the hole that kept two batches of
    # unstamped full-span certs promotion-eligible — the $364k/$246k pair, and v10's $2,017,894
    # cell at -78% DD with 7 liquidations, quoted to the owner as a ~$57/day money-maker.
    #
    # An absent answer is not a good answer. Promotion puts money in front of users; a cert that
    # cannot say whether its window was out-of-sample has not earned that.
    #
    # An explicit argument wins; otherwise the cert answers for itself. Only when NEITHER can say
    # is the answer unknown, and unknown is refused.
    if window_is_in_sample is None:
        window_is_in_sample = capital_cert_window_flag(capital_certification)
    if window_is_in_sample is not False:
        return False
    modes = capital_certification.get("capital_modes")
    if not isinstance(modes, Mapping):
        return False
    # A BANKRUPT spot row is evidence and still fails closed. A MISSING one is not.
    #
    # This used to read `if spot_final is None or _lane_is_bankrupt(...): return False`, so a cert
    # that published no spot cell was refused before the perp lanes were ever read — denying the
    # leverage route that `ml-gate-leverage-capital-cert.md` exists to grant ("marginal or even
    # negative on SPOT but compounding profitably at leverage without liquidating IS a valid,
    # promotable ML signal").
    #
    # MEASURED COST, 2026-08-15, over the 63 certs in `apps/api/models` — 2 books, both real:
    #   btc_usdt_1d/lightgbm/v36                     $10,000 -> $16,165 vs $5,614 B&H = 2.88x,
    #                                                perp_8x, MTM DD -17.4%, 0 liquidations, OOS
    #   btc_usdt_8h/hist_gradient_boosting_clf/v149  $10,000 -> $11,099 vs $7,248 B&H = 1.53x,
    #                                                perp_8x, MTM DD  -5.6%, 0 liquidations, OOS
    # v36 nearly TRIPLED buy-and-hold out-of-sample and was filed as failed because a JSON key
    # was absent. Owner: "ARE YOU MAKING MONKEY CODE?" — the answer was yes, and this is the fix.
    #
    # This widens the gate ONLY where there was never evidence to weigh: `_leverage_route_passes`
    # still demands a liquidation-clean, non-bankrupt lane above the SAME-WINDOW benchmark, and
    # with no benchmark recorded it fails closed as before.
    if _lane_is_bankrupt(modes, _SPOT_LANE):
        return False
    spot_final = _lane_final(modes, _SPOT_LANE)
    bh_final = _spot_bh_final(capital_certification)
    # Best of BOTH routes: a spot lane that grew but trails B&H falls through to the leverage lanes
    # (it used to end the cert there -- 5 of 759 certs, all liq-clean; measured in 9ec98d677).
    if spot_final is not None and capital_backtest_passes(_lane_initial(modes, _SPOT_LANE), spot_final) and _spot_route_passes(modes, bh_final):
        return True
    return _leverage_route_passes(modes, bh_final)


def best_clean_lane_wealth(capital_certification: Mapping[str, Any]) -> dict[str, Any] | None:
    """Richest LIQUIDATION-CLEAN lane, with its same-window B&H and the multiple.

    The number the owner actually asks for -- "how much money, versus just holding BTC?" -- and
    the one no registry row carried, so a `nice_to_have` tier could not be audited without
    re-deriving it by hand.

    Clean is required, not preferred: ranking lanes by final alone promotes the cells that
    liquidated the user, because fixed per-trade sizing keeps account drawdown shallow while
    positions get wiped. Returns None when no clean lane or no benchmark exists -- an
    unanswerable question gets no answer rather than a flattering one.
    """
    bh = _spot_bh_final(capital_certification)
    if bh is None:
        logger.debug("best_clean_lane_wealth: no same-window spot B&H recorded; no answer")
        return None
    best_name: str | None = None
    best_final = 0.0
    best_initial = 0.0
    best_dd: float | None = None
    for name, cell in capital_cert_lanes(capital_certification).items():
        # The three hand-screens that used to sit here (account_bankrupt, account_liquidated and a
        # local liquidation re-parse) are all covered by the SoT screen below, now that it reads the
        # return-book dialect too. Kept as one call so there is a single answer to "is this ruin".
        # THE MTM WIPE IS RUIN TOO — a third copy of the ruin rule that had drifted from the SoT.
        #
        # This screened liquidation and bankruptcy and NOT the mark-to-market wipe, so `1d
        # lightgbm v42`'s perp_7x cell passed it: liquidation_exits 0, account_bankrupt False,
        # max_drawdown -98.9%. The money ledger then printed it as the corpus's TOP performer on
        # unseen data at 4.03x B&H — a cell that took the account to ~zero, ranked first.
        #
        # This does NOT reinstate the reverted -0.40 drawdown floor. Deep drawdown stays DISCLOSED
        # (v10 at -69% and v42's perp_6x at -86.7% are still eligible and still win their books);
        # only the wipe threshold, where the account is gone, is screened. Screening RUIN and
        # screening RISK APPETITE are different questions and only the first belongs here.
        # RANKABLE, not merely NOT-RUINED (corrected 2026-08-25). `capital_is_ruined` deliberately
        # CLEARS a cell whose own final capital disproves its -100% drawdown, because calling those
        # ruined false-KILLs 269 measured corpus cells with zero liquidations. But a cell with a
        # known-broken drawdown must not WIN this ranking either — that is how `1d lightgbm v42`
        # got printed as the corpus's top performer. Untrustworthy is a third state, and only
        # `capital_cell_is_rankable` screens for it.
        from src.domain.services.edge_lifecycle.capital_cert_headline import (
            capital_cell_is_rankable,
        )

        if not capital_cell_is_rankable(cell):
            continue
        raw = cell.get("final_capital", cell.get("final_balance"))
        try:
            final = float(raw)
        except TypeError, ValueError:
            continue
        # DRAWDOWN IS DISCLOSED, NOT SCREENED — corrected the same day I wrote the opposite.
        #
        # I first put a -0.40 floor here, copied from a research helper whose provenance I never
        # checked. Measured against the SoT filter the rest of the stack uses
        # (`capital_cert_headline.headline_exclusion_reason`), that was WRONG in both directions:
        # it disqualifies on RUIN (`liquidated`, `account_bankrupt`, `all_in_leveraged`) and passes
        # a -69% drawdown untouched. Two policies for one question is how a corpus ends up with
        # contradictory tiers.
        #
        # It also mattered in cash: `1d gb v10` is the ONLY book that survives pre-commitment
        # (+23%, $12,298 from $10,000, 2.24x B&H, ZERO liquidations) and it carries -69%. My floor
        # would have deleted the corpus's single survivor from the money ledger.
        #
        # Published drawdown practice is return-relative (CTA rule of thumb: DD <= ~50% of
        # annualised return, i.e. Calmar >= 2), never an absolute cap — so the floor was the wrong
        # SHAPE, not just the wrong number. MONEY-25 tracks introducing that properly, next to the
        # money rather than hidden inside a lane picker.
        dd = _lane_max_drawdown(cell)
        # ABSOLUTE GROWTH. `beats B&H` is a RATIO, and in a falling market a book that loses
        # money still wins it: `8h lightgbm v150` turned $10,000 into $9,457 and ranked seventh
        # on 1.67x, purely because holding lost more. The objective is making money for users,
        # not losing less than BTC did.
        initial = _lane_initial({name: cell}, name)
        if initial and final <= initial:
            continue
        if math.isfinite(final) and final > best_final:
            best_dd = dd
            # Carry the lane's OWN starting capital. A reader that assumes every book is $10k
            # would be hardcoding an unverified premise into the money ledger, and a return
            # multiple is meaningless without the stake it was made on.
            best_name, best_final = name, final
            best_initial = _lane_initial({name: cell}, name)
    if best_name is None:
        logger.debug("best_clean_lane_wealth: no clean, growing, rankable lane; no answer")
        return None
    return {
        "lane": best_name,
        "initial_capital": best_initial,
        "final_capital": best_final,
        "spot_bh_final": bh,
        # DISCLOSED, never used to disqualify. A reader deciding whether to trade this book needs
        # to see that v10's 2.24x came with -69%; hiding it behind a floor is what made the ledger
        # read as if no such book existed.
        "max_drawdown": best_dd,
        "wealth_vs_bh": best_final / bh,
        "beats_bh_wealth": best_final > bh,
        "window_is_in_sample": capital_cert_window_flag(capital_certification),
    }


def build_inapplicable_capital_certification(*, harness: str, reason: str) -> dict[str, Any]:
    """Stamp for leaves that must not fake CryptoBacktester CAPITAL_MODES."""
    return {
        "status": CAPITAL_CERT_STATUS_INAPPLICABLE,
        "harness": harness,
        "reason": reason,
        "realistic_mode": True,
        "capital_modes": {},
    }


def build_pending_capital_certification(*, reason: str | None = None) -> dict[str, Any]:
    """EDGE-eligible cell still waiting for CryptoBT matrix materialization."""
    return {
        "status": CAPITAL_CERT_STATUS_PENDING,
        "reason": reason or "EDGE metrics require CryptoBT capital matrix (spot/3x/5x/8x) before auto-promote",
        "realistic_mode": True,
        "capital_modes": {},
    }


def build_certified_capital_certification(
    *,
    capital_modes: Mapping[str, Any],
    window: Mapping[str, Any] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Persist slim cert block (modes already built via build_capital_lane_row)."""
    modes = dict(capital_modes)
    win = dict(window or {})
    win.setdefault("realistic_mode", True)
    # Probe WITH the window: the gate reads ``window_is_in_sample`` from it and refuses an unknown
    # one, so omitting it here would stamp every cert ``failed`` regardless of its money.
    passes = cryptobt_capital_cert_passes({"status": CAPITAL_CERT_STATUS_CERTIFIED, "capital_modes": modes, "window": win})
    return {
        "status": status or (CAPITAL_CERT_STATUS_CERTIFIED if passes else CAPITAL_CERT_STATUS_FAILED),
        "realistic_mode": True,
        "window": win,
        "capital_modes": modes,
    }


def resolve_promote_capital_pass(
    *,
    verdict: str,
    smoke_initial: float,
    smoke_final: float,
    capital_certification: Mapping[str, Any] | None,
) -> bool:
    """Capital pass used for promote/retention after research_verdict.

    EDGE without a usable cert → False (forces staged CryptoBT). Non-EDGE keeps smoke compound.
    """
    smoke_pass = capital_backtest_passes(smoke_initial, smoke_final)
    if capital_certification is None:
        if verdict == EDGE:
            return False
        return smoke_pass

    status = str(capital_certification.get("status") or "")
    if status == CAPITAL_CERT_STATUS_INAPPLICABLE:
        return smoke_pass
    if status == CAPITAL_CERT_STATUS_PENDING:
        return False
    if status in (CAPITAL_CERT_STATUS_CERTIFIED, CAPITAL_CERT_STATUS_FAILED) or capital_certification.get("capital_modes"):
        return cryptobt_capital_cert_passes(capital_certification)
    if verdict == EDGE:
        return False
    return smoke_pass


def cert_artifact_supports_production_promote(cert: Mapping[str, Any] | None) -> bool:
    """True when a linked capital-cert artifact earns ``production_promoted`` / staging=edge.

    A cert LINK alone is not enough. Measured 2026-08-24: 12 VRP registry rows were
    ``staging=edge`` / ``production_promoted=True`` with ``capital_cert_rel`` pointing at
    ``*_levered_return_cert.json`` where ``funding_modelled=False`` — only spot was publishable,
    while the loop IC stamp still claimed production. Users must not see an IC label as money.

    Levered-return books need funding modelled AND a publishable leverage>1 lane. CryptoBT-shaped
    certs reuse ``cryptobt_capital_cert_passes``. Anything else fails closed.
    """
    if not isinstance(cert, Mapping):
        return False
    harness = str(cert.get("harness") or "")
    if harness == CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK:
        return _levered_return_supports_production_promote(cert)
    if isinstance(cert.get("capital_modes"), Mapping):
        return cryptobt_capital_cert_passes(cert)
    return False


__all__ = [
    "CAPITAL_CERT_STATUS_CERTIFIED",
    "CAPITAL_CERT_STATUS_FAILED",
    "CAPITAL_CERT_STATUS_INAPPLICABLE",
    "CAPITAL_CERT_STATUS_PENDING",
    "CERT_HEADLINE_DSR_KEY",
    "CERT_HEADLINE_DSR_PRESENT_KEY",
    "CERT_WINDOW_IN_SAMPLE_KEY",
    "CERT_WINDOW_KEY",
    # Listed so the re-export is EXPLICIT: mypy's no_implicit_reexport rejects a name that is
    # merely imported here, and `src/cert/grid_persist.py` imports these from this
    # module. Naming them keeps the relocation invisible to every existing consumer.
    "CERT_WINDOW_ROLES",
    "CERT_WINDOW_ROLE_CONFIRM",
    "CERT_WINDOW_ROLE_KEY",
    "CERT_WINDOW_ROLE_SELECT",
    "DISCLOSURE_HEADLINE_DSR_MISSING",
    "MAX_DD_FLOOR",
    "best_clean_lane_wealth",
    "build_certified_capital_certification",
    "build_inapplicable_capital_certification",
    "build_pending_capital_certification",
    "capital_cert_disclosures",
    "capital_cert_headline_deflation_present",
    "capital_cert_lanes",
    "capital_cert_window_flag",
    "capital_cert_window_role",
    "cert_artifact_supports_production_promote",
    "cryptobt_capital_cert_passes",
    "publishable_levered_lanes",
    "resolve_promote_capital_pass",
]
