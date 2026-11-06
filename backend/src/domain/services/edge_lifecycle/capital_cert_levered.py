"""Levered-return book promote predicate (funding modelled + publishable levered lane beating B&H).

Moved verbatim out of ``capital_cert_promote`` (god-split); that module re-exports the public name.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_headline import capital_is_ruined


def publishable_levered_lanes(cert: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Every lane a levered-return cert marks ``publishable``, across all its variants -- the ONE walk
    the promote gate and money-standings both take (it was copied in both until 2026-10-04)."""
    for variant in (cert.get("variants") or {}).values():
        if not isinstance(variant, Mapping):
            continue
        for lane in (variant.get("lanes") or {}).values():
            if isinstance(lane, Mapping) and lane.get("publishable"):
                yield lane


def _levered_return_supports_production_promote(cert: Mapping[str, Any]) -> bool:
    """Funding modelled + publishable leverage>1 lane that beats same-window B&H."""
    if not cert.get("funding_modelled"):
        return False
    bh_raw = cert.get("spot_bh_final", (cert.get("window") or {}).get("spot_bh_final"))
    try:
        benchmark = float(bh_raw)
    except TypeError, ValueError:
        return False
    if not (benchmark > 0.0):
        return False
    for lane in publishable_levered_lanes(cert):
        try:
            lev = float(lane.get("leverage"))  # type: ignore[arg-type]
            final = float(lane["final_capital"])
        except KeyError, TypeError, ValueError:
            continue
        if lev <= 1.0 or capital_is_ruined(lane) or final <= benchmark:
            continue
        return True
    return False
