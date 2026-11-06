"""Lane-cell readers for a capital cert: the two on-disk layouts, per-lane money and drawdown.

Moved verbatim out of ``capital_cert_promote`` (god-split); that module re-exports the public names.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Final

_SPOT_LANE: Final = "spot_10k"
_PERP_3X_LANE: Final = "perp_3x"


def _lane_final(modes: Mapping[str, Any], lane: str) -> float | None:
    row = modes.get(lane)
    if isinstance(row, Mapping):
        for key in ("final_balance", "final_capital"):
            raw = row.get(key)
            if raw is None:
                continue
            try:
                return float(raw)
            except TypeError, ValueError:
                continue
    return None


def _lane_is_bankrupt(modes: Mapping[str, Any], lane: str) -> bool:
    row = modes.get(lane)
    if not isinstance(row, Mapping):
        return False
    return bool(row.get("account_bankrupt"))


def _lane_initial(modes: Mapping[str, Any], lane: str, *, default: float = 10_000.0) -> float:
    row = modes.get(lane)
    if isinstance(row, Mapping):
        raw = row.get("initial_capital")
        if raw is not None:
            try:
                value = float(raw)
            except TypeError, ValueError:
                value = default
            else:
                if value > 0:
                    return value
    return default


def _lane_liquidated(modes: Mapping[str, Any], lane: str) -> bool:
    """Did this lane liquidate? Delegates to the ruin SoT rather than re-parsing the fields.

    This used to reimplement `capital_cert_headline._liquidation_count` line for line, and the
    caller below hand-screened `account_liquidated` next to it because the SoT did not read that
    key. The SoT reads both dialects now, so there is one implementation of "liquidated" again.
    """
    from src.domain.services.edge_lifecycle.capital_cert_headline import (
        EXCLUDED_LIQUIDATED,
        headline_exclusion_reason,
    )

    row = modes.get(lane)
    if not isinstance(row, Mapping):
        return False
    return headline_exclusion_reason(row) == EXCLUDED_LIQUIDATED


def _spot_bh_final(capital_certification: Mapping[str, Any]) -> float | None:
    """Same-window spot B&H final, when the cert recorded one (needed for the leverage route)."""
    for key in ("spot_bh_final", "spot_bh", "bh_final_spot"):
        raw = capital_certification.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except TypeError, ValueError:
            continue
        if math.isfinite(value) and value > 0.0:
            return value
    window = capital_certification.get("window")
    if isinstance(window, Mapping):
        return _spot_bh_final(window)
    return None


def capital_cert_lanes(capital_certification: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Every lane cell in a cert, from EITHER of the two shapes on disk.

    Two engines write two layouts and nothing in `src/` read the second one, which is why every
    registry row reports `capital_final: null` while 29 certs hold real money:

    * `capital_modes.<lane>`                          -> the cell directly
    * `capital_x_exit.best_by_capital_lane.<lane>.best` -> the cell one level down

    Measured 2026-08-10: reading only the first finds ONE cert of 42 with money and would
    support the conclusion "the corpus is empty". Reading both finds 29. A verdict drawn from
    one drawer of a two-drawer artifact is the same defect as ranking `combo_top25` and calling
    it the grid.
    """
    lanes: dict[str, Mapping[str, Any]] = {}
    # `capital_x_exit` FIRST — it is written by the run that also refreshed `window` and
    # `spot_bh_final`, so its lanes belong to the SAME window as the benchmark they are divided
    # by. `capital_modes` is the legacy block and a re-cert does not always rewrite it.
    #
    # Preferring `capital_modes` produced a live fantasy on 2026-08-10: prod v2 re-certified
    # onto a 25-day unseen window (B&H $10,184, best clean lane $10,063 — it LOSES), while
    # `capital_modes` still held the stale in-sample $234,317. The ledger divided one by the
    # other and published **23.01x B&H**. A stale numerator over a fresh denominator is not a
    # small error; it is the exact species of number this corpus spent a session deleting.
    for key in ("capital_x_exit", "orphaned_capital_x_exit"):
        block = capital_certification.get(key)
        if not isinstance(block, Mapping):
            continue
        by_lane = block.get("best_by_capital_lane")
        if not isinstance(by_lane, Mapping):
            continue
        for name, wrapper in by_lane.items():
            if not isinstance(wrapper, Mapping):
                continue
            cell = wrapper.get("best")
            if isinstance(cell, Mapping) and str(name) not in lanes:
                lanes[str(name)] = cell
    # Legacy block — consulted ONLY when the grid engine wrote nothing at all.
    #
    # Emphatically NOT per-lane. Filling individual gaps from `capital_modes` reintroduces the
    # fantasy in a subtler form: on prod v2's 25-day re-cert the grid produced no publishable
    # `spot_10k` cell, so a per-lane fallback supplied the stale IN-SAMPLE $29,675 and the
    # ledger reported 2.91x against the fresh $10,184 benchmark. The perp lanes, which the grid
    # DID write, all sat near $10k and LOSE to holding.
    #
    # If the grid ran, its answer is authoritative INCLUDING "this lane produced nothing".
    # A silent stale substitute is worse than an absent lane, because absence is visible.
    if not lanes:
        direct = capital_certification.get("capital_modes")
        if isinstance(direct, Mapping):
            for name, cell in direct.items():
                if isinstance(cell, Mapping):
                    lanes[str(name)] = cell
    return lanes


# Honest mark-to-market drawdown floor for a CITABLE lane.
#
# Owned HERE, in the domain layer, on purpose. The same -0.40 lives in
# `src/research/edge_hunt/edge_inventory_cryptobacktest_helpers.DEFAULT_MAX_DD_FLOOR`, and a
# domain service importing a research script would invert the dependency direction. The research
# scripts should converge on this constant; until they do, the two must agree and this docstring
# is the record of why there are two names for one policy number.
MAX_DD_FLOOR = -0.40

_DD_KEYS = ("max_drawdown", "max_drawdown_pct", "mtm_max_drawdown")


def _lane_max_drawdown(cell: Mapping[str, Any]) -> float | None:
    """Honest MTM drawdown for a lane cell, as a NEGATIVE fraction, or None when absent.

    Accepts both the flat lane shape and the `{"best": {...}}` shape the combo grid writes, and
    normalises a percentage (-72.3) to a fraction (-0.723). Returns None rather than 0.0 when the
    field is missing: an unrecorded drawdown must not read as a flawless one, which is the
    fail-open that let unrecorded sizing publish fantasy cells (commit e2350cdc5).
    """
    source: Mapping[str, Any] = cell
    inner = cell.get("best")
    if isinstance(inner, Mapping):
        source = inner
    for key in _DD_KEYS:
        raw = source.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except TypeError, ValueError:
            continue
        if not math.isfinite(value):
            continue
        if value > 0:  # some writers store magnitude; a drawdown is a loss
            value = -value
        return value / 100.0 if value < -1.0 else value
    return None
