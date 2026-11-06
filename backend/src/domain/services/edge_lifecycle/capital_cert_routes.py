"""The spot and leverage routes of the capital-cert promote gate.

Moved verbatim out of ``capital_cert_promote`` (god-split).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_lanes import (
    _PERP_3X_LANE,
    _SPOT_LANE,
    _lane_final,
    _lane_initial,
    _lane_is_bankrupt,
    _lane_liquidated,
)


def _spot_route_passes(modes: Mapping[str, Any], bh_final: float | None = None) -> bool:
    """Spot grew — require the min-lev lane to exist and not be wiped, and to BEAT HOLDING.

    The perp_3x requirement belongs to THIS route only (its original meaning: "spot grew AND
    min-lev survived"). The leverage route must not demand it, or a cert whose winning lane is
    perp_5x would be rejected for lacking a perp_3x row.

    THE ASYMMETRY THIS CLOSES. The leverage route has always required `lane_final > bh_final`;
    this route required only that spot GREW. So $10,000 -> $10,100 passed while holding made
    $12,000, and the identical book at leverage did not — two routes, two different bars, for
    the same question ("did this make the user money?"). `main-objective-find-profitable-signal`
    is explicit that the honest gate is beats-B&H, not "ended above the stake".

    MEASURED BEFORE CHANGING IT (`investigate-before-changing-a-gate`), over the 63
    `capital_certification.json` in `apps/api/models`: 8 pass, 4 of them via this route, and
    **0 of those 4 lose to B&H**. On the ML corpus alone this edit is a no-op — which is exactly
    the 2026-08-05 trap, so it would not be worth making for that corpus.

    It is worth making because the SAME predicate gates the CONTINUOUS-book corpus, where the
    shape is live: `lowvol 1d` printed `status=certified` + `promote_gate=True` beside
    `beats_bh=False`, and VT-17's 1h leaf grew to $11,654 while holding made $12,062. Reading
    only `apps/api/models` and concluding "no impact" would be the one-drawer mistake this file
    already documents in `capital_cert_lanes`.

    FAILS OPEN on a missing benchmark, deliberately and unlike the leverage route. There, no
    benchmark means the claim ("beats holding at leverage") cannot be made at all. Here the
    original claim ("spot grew") is still fully evidenced, so refusing it would invalidate every
    legacy cert on a technicality rather than on a finding.
    """
    if _lane_is_bankrupt(modes, _PERP_3X_LANE):
        return False
    perp_3x_final = _lane_final(modes, _PERP_3X_LANE)
    if perp_3x_final is None or perp_3x_final <= 0.0:
        return False
    if bh_final is None:
        return True
    spot_final = _lane_final(modes, _SPOT_LANE)
    return spot_final is not None and spot_final > bh_final


def _lane_is_unlevered(modes: Mapping[str, Any], lane: str) -> bool:
    """True when this cell carries NO leverage, whatever its dict key is spelled.

    MEASURED 2026-08-28. This used to be `lane == _SPOT_LANE`, an exact-key comparison, and
    `build_strategy_sleeve_capital_cert` keys its cells `lane_size` — `spot_10k`, `spot_10k_2pct`,
    `spot_10k_10pct`, `perp_3x`, `perp_3x_2pct`. So every REDUCED-SIZING SPOT cell was iterated as
    though it were a leverage lane. 12 of the 16 certs on disk carrying a `promote_gate` hold cells
    in that shape.

    What it cost, on `cross_venue_basis/execsim_BTC_USDT_4h.json`: all-in spot ends at $8,973,
    below its $10,000 start, so the spot route correctly failed — and then `spot_10k_2pct` at
    $9,978 cleared the $9,830 buy-and-hold and PASSED THROUGH THE LEVERAGE ROUTE. A 2%-sized spot
    book was certified as "money at leverage", on all five HTF timeframes.

    That inverts the claim the route exists to grant. `ml-gate-leverage-capital-cert.md` grants
    "marginal or even negative on SPOT but compounding profitably AT LEVERAGE without liquidating".
    Taking LESS spot exposure is the opposite: the same book, de-risked, losing less.

    Keyed on the row's own `leverage` value so it holds for any future key scheme, with the key
    PREFIX as the fallback for older certs written before cells carried the field. Unknown reads
    as unlevered — a cell that cannot say it is levered has not earned the leverage route.
    """
    row = modes.get(lane)
    if isinstance(row, Mapping) and row.get("leverage") is not None:
        try:
            return float(row["leverage"]) <= 1.0
        except TypeError, ValueError:
            return True
    return lane == _SPOT_LANE or lane.startswith(f"{_SPOT_LANE}_")


def _leverage_route_passes(modes: Mapping[str, Any], bh_final: float | None) -> bool:
    """Spot route failed — leverage money counts only from a SURVIVING LEVERED lane beating spot B&H.

    Fails closed without a same-window benchmark: with nothing to beat the claim cannot be made.
    """
    if bh_final is None:
        return False
    for lane in modes:
        if _lane_is_unlevered(modes, lane) or _lane_is_bankrupt(modes, lane) or _lane_liquidated(modes, lane):
            continue
        lane_final = _lane_final(modes, lane)
        if lane_final is None or not math.isfinite(lane_final) or lane_final <= bh_final:
            continue
        # AND IT MUST HAVE MADE MONEY. Beating a FALLING benchmark is not the same as compounding,
        # and only one of those is a product a user should be put into.
        #
        # The asymmetry this removes: the SPOT route above already demands
        # `capital_backtest_passes` — absolute growth — AND beating B&H. This route demanded only
        # the second, so a levered lane ending BELOW its own starting capital promoted whenever BTC
        # fell further. MEASURED on `cross_venue_basis/execsim_BTC_USDT_4h.json`: `perp_3x_2pct`
        # ends at $9,935 of $10,000 and clears a $9,830 buy-and-hold.
        #
        # `ml-gate-leverage-capital-cert.md` grants this route to a book "COMPOUNDING PROFITABLY at
        # leverage without liquidating". $9,935 on $10,000 has not compounded profitably, and a
        # user in CASH beat it. The gate was more permissive than the rule it implements.
        #
        # Corpus count before changing it (investigate-before-changing-a-gate): of every cert on
        # disk, exactly 5 pass this predicate today and all 5 flip — so this costs no legitimate
        # book its pass. An unknown initial is not a pass: it cannot show growth.
        lane_initial = _lane_initial(modes, lane)
        if lane_initial is None or lane_final <= lane_initial:
            continue
        return True
    return False
