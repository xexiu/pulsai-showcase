"""A user must never wait on the Coinglass vendor when a recent snapshot exists.

MEASURED ON PROD, 2026-09-06, three consecutive sweeps of the published GET surface:

    GET /api/v1/market/derivatives-flow   1684ms / 1682ms / 1684ms   (budget 200ms)

Reproducible to the millisecond because it is not our compute: on a cache MISS the handler
calls Coinglass and waits. `DERIVATIVES_FLOW_CACHE_TTL_S` is 120s, so the entry is simply GONE
121 seconds after it was written and the next visitor pays the full vendor round-trip.

I first called this "explained, not a defect" -- the TTL bounds how OFTEN it happens. That was
too comfortable, and it is exactly the owner's opening complaint: *"an unlucky user will still
grind to slow requeste? where is the perf then? i tought thst all is prewarm, precache."*
Bounding the frequency of a 1.7s wait is not the same as nobody waiting.

THE FIX, stale-while-revalidate: keep the snapshot in Redis well past the point it stops being
FRESH, and treat the two windows separately.

  * within the fresh window  -> serve it, do nothing else;
  * past fresh, within stale -> serve it IMMEDIATELY and refresh in a detached task;
  * past stale (or absent)   -> only then does anyone wait on the vendor.

The detached-refresh shape is not invented here: `schedule_detached_cache_fill` already exists
for precisely this -- own task, outside the caller's cancel scope, never raises into the
caller. Reused rather than re-derived.

REUSE-AUDIT: the resolver and the stale window live in
`shared/constants/derivatives_flow_cache.py`, which already declares itself the "Redis cache
SoT for derivatives-flow snapshots" (it holds the key prefix) -- not in
`shared/constants/derivatives_flow.py`, which is the OVERLAY SoT (limits, source/quality
enums, warning templates). Also considered market_chart_indicators_response_cache (in-process
LRU keyed by bar close: rotates on a CLOCK with no vendor behind it, so no stale window
applies). No existing helper expresses "fresh vs stale" over one Redis entry.
"""

from __future__ import annotations

from src.shared.constants.derivatives_flow import DERIVATIVES_FLOW_CACHE_TTL_S
from src.shared.constants.derivatives_flow_cache import (
    DERIVATIVES_FLOW_STALE_TTL_S,
    derivatives_flow_snapshot_freshness,
)


class TestTheTwoWindowsAreDistinct:
    """The whole point: 'still usable' must outlive 'still fresh'."""

    def test_the_stale_window_is_longer_than_the_fresh_one(self) -> None:
        assert DERIVATIVES_FLOW_STALE_TTL_S > DERIVATIVES_FLOW_CACHE_TTL_S, (
            "if the entry expires when it stops being fresh there is nothing to serve stale, "
            "and every visitor past the TTL waits on Coinglass -- the measured 1684ms"
        )

    def test_a_just_written_snapshot_is_fresh(self) -> None:
        assert derivatives_flow_snapshot_freshness(age_seconds=0.0) == "fresh"

    def test_a_snapshot_just_inside_the_fresh_window_is_fresh(self) -> None:
        assert derivatives_flow_snapshot_freshness(age_seconds=DERIVATIVES_FLOW_CACHE_TTL_S - 1) == "fresh"

    def test_a_snapshot_past_the_fresh_window_is_stale_not_gone(self) -> None:
        """THE REGRESSION THIS PINS: at 121s the old code had nothing and called the vendor."""
        assert derivatives_flow_snapshot_freshness(age_seconds=DERIVATIVES_FLOW_CACHE_TTL_S + 1) == "stale"

    def test_a_snapshot_past_the_stale_window_is_expired(self) -> None:
        assert derivatives_flow_snapshot_freshness(age_seconds=DERIVATIVES_FLOW_STALE_TTL_S + 1) == "expired"

    def test_the_boundaries_are_inclusive_of_fresh_then_stale(self) -> None:
        """Pinned because an off-by-one here silently turns stale-serving back into waiting."""
        assert derivatives_flow_snapshot_freshness(age_seconds=DERIVATIVES_FLOW_CACHE_TTL_S) == "stale"
        assert derivatives_flow_snapshot_freshness(age_seconds=DERIVATIVES_FLOW_STALE_TTL_S) == "expired"


class TestItNeverMisreadsAClockGlitch:
    """A negative age means the clock moved; serving is right, waiting on the vendor is not."""

    def test_a_negative_age_is_treated_as_fresh(self) -> None:
        assert derivatives_flow_snapshot_freshness(age_seconds=-5.0) == "fresh"
