"""Redis cache SoT for derivatives-flow snapshots."""

from __future__ import annotations

from typing import Final

DERIVATIVES_FLOW_CACHE_KEY_PREFIX: Final[str] = "derivatives-flow:"

DERIVATIVES_FLOW_STALE_TTL_S: Final[int] = 900
"""How long a snapshot stays USABLE after it stops being FRESH.

Two windows, deliberately different, because they answer different questions:

    DERIVATIVES_FLOW_CACHE_TTL_S (120s)  "is this current enough to serve without refreshing?"
    DERIVATIVES_FLOW_STALE_TTL_S (900s)  "is this still better than making the user wait on
                                          Coinglass?"

MEASURED on prod 2026-09-06, three consecutive sweeps: ``GET /api/v1/market/derivatives-flow``
took 1684ms / 1682ms / 1684ms against a 200ms budget. Reproducible to the millisecond because
it is a VENDOR round-trip, not our compute -- the Redis entry simply expired at 120s and the
next visitor paid for it. One TTL cannot express both questions, so the entry died at the
moment it merely became slightly old.

900s (15 min) rather than "forever": open interest and liquidation history are market data,
and a quarter-hour-old overlay is worth showing while a fresh one loads. Beyond that, waiting
is the honest answer. Raise it only against a measurement of how stale users tolerate.
"""


def derivatives_flow_snapshot_freshness(*, age_seconds: float) -> str:
    """Classify a cached snapshot by age: ``fresh`` | ``stale`` | ``expired``.

    ``stale`` is the state that did not exist before, and it is the whole point: serve it NOW
    and refresh behind the request, so vendor latency lands on a background task instead of on
    a person.

    A NEGATIVE age is treated as fresh. It means the clock moved (NTP step, container
    restart), and the safe reading of "I cannot tell how old this is" is to serve what we have
    -- the alternative is a vendor round-trip triggered by a clock glitch.
    """
    from src.shared.constants.derivatives_flow import DERIVATIVES_FLOW_CACHE_TTL_S

    if age_seconds < DERIVATIVES_FLOW_CACHE_TTL_S:
        return "fresh"
    if age_seconds < DERIVATIVES_FLOW_STALE_TTL_S:
        return "stale"
    return "expired"
