"""Is this cell's Sharpe measurable at all, and how far from established is it?

IMPORTERS/CALLERS: src/domain/services/edge_lifecycle/capital_cert_headline.py,
    src/domain/services/edge_lifecycle/precommit_selection.py,
    src/application/services/money_ledger_ruin.py, src/cert/grid_rank.py,
    src/cert/cell_selection.py,
    src/research/edge_hunt/run_edge_capital_x_exit_grid.py,
    run_select_confirm_cert.py and run_select_confirm_cert_record.py -- each repointed at this
    module directly.
AFFECTED API: nothing moves. `required_track_record` and `is_thin_sample` keep their names and
    signatures; only the module they are imported from changes.
DATA SCHEMAS: none persisted. Reads the cert cell mapping keys `num_trades`, `sharpe_ratio`,
    `return_skew`, `return_kurtosis`, `annualization_factor`.

LAYER (DDD_PATTERNS.md decision matrix): a DOMAIN SERVICE. "Does it contain business rules?" --
yes: the acquit-only policy below is a rule about what this business will accept as evidence, not
a data transformation, and it belongs to no single entity. It depends only on the pure statistics
layer beneath it and on nothing above, so the dependency direction stays inward.

PATTERN (ARCHITECTURE_PATTERNS.md §3.1): NONE is invoked, deliberately. This is a module split;
the three definitions move verbatim. Two anti-fits decided the shape. §9.2 over-abstraction --
adding a Strategy or Factory here would be indirection with no variation behind it, since there
is exactly one rule. §2 Adapter -- "an adapter between two things we control is usually two things
that should have agreed", which is why capital_cert_headline does NOT re-export these as a
compatibility shim: every caller imports from here instead, so there is one import path and
nothing to drift.

EXTRACTED from capital_cert_headline.py on 2026-09-18, when that file stood at 632 lines against
a 536 ratchet entry and a 400-line standard -- and the 96 lines of growth were exactly these
three. The seam is real rather than convenient: everything left in that module answers "which
cell is the headline", while these three answer a prior and independent question -- whether the
cell's Sharpe can be believed at the sample size it was measured on. One is selection; the other
is measurement.

REUSE-AUDIT: considered src/domain/services/min_track_record_length.py -- the closed forms
    `min_track_record_length` and `has_sufficient_track_record` (Bailey & Lopez de Prado 2012)
    live there and are IMPORTED here, never reimplemented; not extending it because it is the
    pure statistics layer and knows nothing about a cert cell's field names or the acquit-only
    policy. Considered src/domain/services/edge_lifecycle/gate.py -- IMPORTED here for the
    MIN_TRADES_FOR_SHARPE fallback floor, so the flat number has one owner; it depends on
    nothing in this package, so no import cycle is created. Considered
    src/domain/services/edge_lifecycle/capital_cert_headline.py -- this module is an EXTRACTION
    FROM it. Considered src/application/services/money_ledger_ruin.py -- a CONSUMER of
    is_thin_sample, pure mapping logic with no statistics of its own. Read the one body-clone
    cluster in this package first: `_shape_best_exit` / `_shape_hold_sweep` in
    capital_cert_history.py, which reshape artifact sub-objects and carry no statistics.

THE POLICY THESE ENCODE, and the reason it is asymmetric. MinTRL may ACQUIT, never CONVICT
(owner, 2026-09-18: "too strict/very conservative"). `_derived_thin_verdict` used to decide
outright, which turned the closed form into a kill criterion: prod `1d v2` confirms on 281-303
trades while MinTRL wants 3,089-5,520, so every cert written since the moments were persisted
would flip it candidate -> nice_to_have on a bar no book in this corpus has ever cleared. It
convicted `4h v411` at 738 trades the same way. A strong book may therefore clear thinness on
FEWER trades than the flat floor demands -- information the floor cannot express -- but a book
that clears the floor is never re-condemned by the closed form. `required_track_record` keeps
the gap visible either way, because a number computed and never written is how this corpus has
lost evidence before.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from src.domain.services.min_track_record_length import (
    has_sufficient_track_record,
    min_track_record_length,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

#: The flat thin-sample floor -- the FALLBACK of `is_thin_sample` when a cell carries no moments for
#: MinTRL. It lives here, beside the derivation it backs up. Thinness is a DISCLOSURE beside the result,
#: never a veto (owner, 2026-10-04: everything in this repo is educational and research/money gates
#: must not be strict); until that day `gate.implausible_metrics` held a second, flat thin-sample rule
#: that nulled the verdict. `gate` re-exports this name so its 17 importers keep one definition.
MIN_TRADES_FOR_SHARPE: Final = 100

logger = logging.getLogger(__name__)

__all__ = ["is_thin_sample", "required_track_record"]


def required_track_record(cell: Mapping[str, Any]) -> float | None:
    """Trades MinTRL says THIS cell's Sharpe needs, or None when the cell cannot be asked.

    The disclosure half of the acquit-only rule in `is_thin_sample`. Since MinTRL no longer decides
    the tier, the number it produces has to stay VISIBLE or the evidence gap silently disappears —
    which is the failure this corpus keeps paying for (a value computed, described in a comment,
    and never written). A reader comparing this against `num_trades` can see exactly how far a book
    is from established, without the grader turning that distance into a kill.
    """
    factor = cell.get("annualization_factor")
    skew = cell.get("return_skew")
    kurtosis = cell.get("return_kurtosis")
    sharpe = cell.get("sharpe_ratio")
    if factor is None or skew is None or kurtosis is None or sharpe is None:
        return None
    try:
        per_observation = float(sharpe) / float(factor)
    except TypeError, ValueError, ZeroDivisionError:
        # OURS, as in `_derived_thin_verdict`: we wrote these fields, so unreadable is a writer defect.
        logger.warning("cert cell carries unreadable MinTRL inputs (sharpe=%r, annualization_factor=%r)", sharpe, factor)
        return None
    return min_track_record_length(sharpe=per_observation, skew=float(skew), kurtosis=float(kurtosis))


def _derived_thin_verdict(cell: Mapping[str, Any], trades: int) -> bool | None:
    """MinTRL's answer for this cell, or None when the cell cannot be asked.

    The Sharpe on a cert cell is ANNUALIZED; MinTRL takes it at the periodicity of the observations
    it counts, which here is per trade -- hence the division by the recorded factor. Feeding the
    annualized number in would demand ~1 observation of everything, which is the opposite of a gate.
    """
    factor = cell.get("annualization_factor")
    skew = cell.get("return_skew")
    kurtosis = cell.get("return_kurtosis")
    sharpe = cell.get("sharpe_ratio")
    if factor is None or skew is None or kurtosis is None or sharpe is None:
        # ORDINARY: every cell written before 2026-09-17 predates the moments. Silent on purpose --
        # the caller falls back to the flat floor, which is what those cells were graded against.
        return None
    try:
        per_observation = float(sharpe) / float(factor)
    except TypeError, ValueError, ZeroDivisionError:
        # OURS: we wrote these fields, so unreadable values are a defect in the writer, not an old
        # cell. Same shape, opposite meaning -- said out loud so the two cannot be confused.
        logger.warning(
            "cert cell carries unreadable MinTRL inputs (sharpe=%r, annualization_factor=%r); falling back to the flat trade floor",
            sharpe,
            factor,
        )
        return None
    sufficient = has_sufficient_track_record(
        observations=trades,
        sharpe=per_observation,
        skew=float(skew),
        kurtosis=float(kurtosis),
    )
    if sufficient is None:
        # MinTRL is undefined when the Sharpe does not beat the benchmark -- and a book that does
        # not beat "not trading" is exactly what THIN is meant to keep out of a headline.
        return True
    return not sufficient


def is_thin_sample(cell: Mapping[str, Any], *, min_trades: int = MIN_TRADES_FOR_SHARPE) -> bool:
    """True when there are too few trades for the cell's Sharpe to mean anything.

    DERIVED, not picked, whenever the cell carries the moments: ``min_track_record_length``
    (Bailey & Lopez de Prado 2012) says how many observations THIS Sharpe needs, given its skew and
    kurtosis. ``MIN_TRADES_FOR_SHARPE = 100`` was calibrated from a single anecdote and is wrong in
    both directions -- v42's confirm cleared it at SR 0.263 over exactly 100 trades while proving
    nothing, and a book at SR 2.0 is refused at 99 trades though the closed form needs a handful.

    The flat floor remains the FALLBACK, and deliberately so: every cell written before the moments
    were persisted (2026-09-17) carries none, and answering those from a different rule would
    silently re-grade the whole corpus on a number it was never measured against.

    Unknown trade count counts as thin: unmeasured is not the same as adequate.
    """
    raw = cell.get("num_trades")
    if raw is None:
        return True
    try:
        trades = int(raw)
    except TypeError, ValueError:
        return True
    # MinTRL may ACQUIT, never CONVICT (2026-09-18, owner: "too strict/very conservative").
    #
    # `_derived_thin_verdict` used to decide outright, which made the closed form a KILL criterion.
    # Measured: prod `1d v2` confirms on 281-303 trades and MinTRL wants 3,089-5,520 of them, so the
    # moment its cert carries the moments — every cert written since 2026-09-17 does — a re-cert
    # flips it `candidate` -> `nice_to_have` on a bar no book in this corpus has ever cleared. The
    # same closed form convicted `4h v411` at 738 trades.
    #
    # So the direction is asymmetric on purpose, and it matches `.claude/rules` on thinness being a
    # DISCLOSURE beside the money rather than a verdict that erases it: a STRONG book may clear
    # thinness on fewer trades than the flat floor demands (MinTRL says so, and that is information
    # the floor cannot express), but a book that clears the floor is never re-condemned by it. The
    # requirement stays in the artifact for the reader either way.
    if _derived_thin_verdict(cell, trades) is False:
        return False
    return trades < min_trades
