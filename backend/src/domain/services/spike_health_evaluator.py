"""Pure spike-health evaluator (Twitter spike readiness — T1-5).

Consumes the shared compact-view shape produced by the observability
modules (``db_metrics`` / ``endpoint_metrics`` / ``redis_metrics`` /
``event_loop_lag``)::

    {"windows": [...], "primary_window": "1m", "by_label": {window: {label: entry}}}

where each ``entry`` carries ``count`` and a precomputed ``status`` from
:func:`~src.infrastructure.observability._compact_view_helpers.compute_threshold_status`.

This module is intentionally **pure** (no IO, no clock, no settings): it
reduces the per-label statuses across all sources into one worst-of
verdict plus the offending entries, so it is trivially unit-testable and
fast (well within the perf baselines). The IO — gathering views, logging,
throttling, paging — lives in the application/watcher layer.

@see src/api/lifespan/spike_watch.py (orchestration + tick loop)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, TypeGuard

from src.shared.constants.observability_metrics import (
    EVENT_LOOP_LAG_LABEL,
    EVENT_LOOP_SOURCE,
)
from src.shared.constants.spike_alert import (
    COMPACT_STATUS_OK,
    COMPACT_STATUS_UNKNOWN,
)
from src.shared.constants.spike_alert import (
    status_severity as _severity,
)


@dataclass(frozen=True)
class SpikeHealthOffender:
    """One degraded compact-view entry contributing to the verdict."""

    source: str
    window: str
    label: str
    status: str
    p95: float | None
    #: Worst single observation in the window, when the source reports one.
    #:
    #: Only the event-loop view does today, and it is the reason this field exists: a stall is
    #: ONE sample among hundreds, so its p95 is ~0 while its worst sample IS the incident.
    #: Ranking and rendering on p95 alone put the CAUSE last on a page whose offender list is
    #: capped at five -- that is, dropped it, in favour of the endpoints it froze.
    worst: float | None = None
    #: How many observations the window held when this offender was judged.
    #:
    #: A p95 means nothing without it. Measured 2026-09-06: organic traffic on the chart routes
    #: is 1-2 requests per 5-minute window, so a "p95" there is the slower of two -- which is
    #: exactly why `min_samples` discards those windows. But once a window PASSES the floor the
    #: count was thrown away, and 20 samples versus 2000 mean opposite things: the first is a
    #: burst clearing the bar, the second is real load. Carried here so the page, and the row
    #: persisted from it, can be audited afterwards instead of reconstructed from process
    #: timing. None when the source does not report a count.
    sample_count: int | None = None
    #: The event loop's WORST stall in this same snapshot, when that stall is on its own large
    #: enough to account for this offender's p95. ``None`` means the loop does not explain it —
    #: either it was healthy, or it was never measured.
    #:
    #: The dependency bands time the whole ``await``, which for Redis contains a connection-pool
    #: acquisition and a suspension point, so the number is service time PLUS our own queueing.
    #: That has twice put a healthy dependency on a page: ``redis GET p95=0.425s`` on 2026-08-07
    #: (Redis measured 5.47 ms minutes later) and ``redis EXISTS p95=0.227s`` on 2026-09-06 (the
    #: same container measured 8.33 ms).
    #:
    #: The rule needs no tuned ratio: an await spanning a stall of L measures at least L, so a
    #: worst sample >= p95 accounts for the whole percentile with no dependency slowness at all.
    #:
    #: It must be compared against the loop's ``max``, never its p95. The loop samples on a fixed
    #: interval across a window minutes long while a dependency's p95 is dominated by whatever
    #: burst produced its samples — measured 2026-09-06, one dashboard load gave
    #: ``redis EXISTS p95 0.173s`` beside ``event_loop p95 0.002s, max 0.219s``. Comparing the
    #: percentiles is what cleared the loop on both earlier investigations.
    explained_by_loop_stall_seconds: float | None = None

    def as_log_row(self) -> dict[str, Any]:
        """Field set for the degraded-health log record, carrying what DECIDED the status.

        Lives on the dataclass because the dataclass owns these fields. It was built inline at
        the log call, which is how it came to emit `p95` alone: the event-loop status is
        `worst_status(p95, MAX)`, so a stall is `critical` on its MAX while its p95 sits near
        zero, and a record showing only the percentile contradicts its own verdict. Measured on
        prod 2026-09-08 19:15: `status="critical" ... "p95":0.00084` -- 300x UNDER the threshold
        it appeared to be failing.
        """
        return {
            "source": self.source,
            "label": self.label,
            "window": self.window,
            "status": self.status,
            "p95": self.p95,
            "worst": self.worst,
            "samples": self.sample_count,
        }


@dataclass(frozen=True)
class SpikeHealthVerdict:
    """Worst-of status across all sources, with the degraded entries."""

    status: str
    offenders: tuple[SpikeHealthOffender, ...]


def evaluate_spike_health(
    views: dict[str, dict[str, Any]],
    *,
    min_samples: int,
) -> SpikeHealthVerdict:
    """Reduce per-source compact views to a single worst-of verdict.

    For each source's ``primary_window``, every label entry is considered
    except those with no data (``unknown``) or fewer than ``min_samples``
    observations — both are too thin to page on. The verdict status is the
    most severe remaining status (``ok`` when nothing qualifies); offenders
    are the ``warn``/``critical`` entries, sorted by severity and then by the
    value that drove the status — a source's ``max`` when it reports one,
    otherwise its ``p95``.

    :param views: Mapping of source name → compact-view dict.
    :param min_samples: Minimum window sample count before a status alerts.
    :returns: A :class:`SpikeHealthVerdict`.
    """
    offenders: list[SpikeHealthOffender] = []
    worst = COMPACT_STATUS_OK

    for source, view in views.items():
        primary = view.get("primary_window")
        by_label = view.get("by_label", {})
        window_block = by_label.get(primary, {}) if primary is not None else {}
        for label, entry in window_block.items():
            status = entry.get("status", COMPACT_STATUS_UNKNOWN)
            if status == COMPACT_STATUS_UNKNOWN:
                continue
            if int(entry.get("count", 0)) < min_samples:
                continue
            if _severity(status) > _severity(worst):
                worst = status
            if _severity(status) > _severity(COMPACT_STATUS_OK):
                offenders.append(
                    SpikeHealthOffender(
                        source=source,
                        window=str(primary),
                        label=str(label),
                        status=status,
                        p95=entry.get("p95"),
                        worst=entry.get("max"),
                        # The count is already in hand -- it was just used against min_samples
                        # two lines above -- and throwing it away is what made a past page
                        # un-auditable. Carried through so the persisted row can answer
                        # "20 samples or 2000?", which is the question that separates a burst
                        # from real load.
                        sample_count=entry.get("count"),
                    )
                )

    # Rank on the number that DROVE the status, not always on p95. A stalled event loop has a
    # near-zero p95 by construction -- one sample among hundreds -- and a huge worst sample, so a
    # p95-only sort files the CAUSE below every endpoint it froze, on a page that shows five.
    offenders.sort(key=lambda o: (_severity(o.status), o.worst or o.p95 or 0.0), reverse=True)
    attributed = _attribute_loop_stall(offenders, _loop_worst_stall_seconds(views))
    return SpikeHealthVerdict(status=worst, offenders=tuple(attributed))


def _loop_worst_stall_seconds(views: dict[str, dict[str, Any]]) -> float | None:
    """The loop's worst sample in its primary window, or ``None`` if it was never measured.

    Read from the SAME snapshot the offenders came from, so the two numbers describe one moment.
    Deliberately ignores ``min_samples``: the question is not "should the loop page?" but "how
    long did the loop demonstrably stop?", and a stall that is real evidence at 3 samples is
    still real evidence when it is too thin to alert on by itself.
    """
    view = views.get(EVENT_LOOP_SOURCE)
    if not view:
        return None

    # PREFER THE ATTRIBUTION SPAN over the status window, because the two are sized for
    # different questions and only one of them is comparable to the offender.
    #
    # The loop's own window is 2 minutes; every dependency is judged on 5. Measured on prod
    # 2026-09-06, redis EXISTS reported a byte-identical p95 (0.0691687276586890) at 23:29 and
    # 23:30 while its explanation went 0.354s -> None, purely because the stall had aged out
    # here. The victim then looked unexplained for the remaining three minutes of the window it
    # was still polluting, and paged.
    #
    primary = view.get("primary_window")
    entry = view.get("by_label", {}).get(primary, {}).get(EVENT_LOOP_LAG_LABEL) if primary is not None else None
    if not entry or not entry.get("count"):
        return None

    # Falls through when the key is absent, so an older snapshot -- or any other producer of
    # this view shape -- still attributes from `max` exactly as before rather than silently
    # stopping. Read from the ENTRY rather than the view's top level: the shared compact shape
    # is exactly {windows, primary_window, by_label} and two contract tests enforce it.
    attribution = entry.get("attribution_max_seconds")
    if _is_real_number(attribution):
        return float(attribution)
    worst = entry.get("max")
    if not _is_real_number(worst):
        return None
    return float(worst)


def _is_real_number(value: Any) -> TypeGuard[int | float]:
    """True for an int or float that is genuinely a measurement.

    `bool` is a SUBCLASS of `int`, so a plain isinstance check reads a JSON `true` as a
    1.0-second stall and attributes every offender in the snapshot to it. Extracted the moment a
    second caller needed the same guard, rather than copied -- a duplicated type check is exactly
    how one of the two copies later loses the bool clause.
    """
    return isinstance(value, int | float) and not isinstance(value, bool)


def _attribute_loop_stall(
    offenders: list[SpikeHealthOffender],
    loop_worst_seconds: float | None,
) -> list[SpikeHealthOffender]:
    """Mark each dependency offender the loop's worst stall can account for on its own.

    Attribution NEVER changes the status or drops an offender. A stalled loop is a real
    incident and the page must still fire; the only thing this changes is WHICH subsystem the
    page names, which twice was the wrong one.
    """
    if loop_worst_seconds is None:
        return offenders

    attributed: list[SpikeHealthOffender] = []
    for off in offenders:
        if off.source == EVENT_LOOP_SOURCE:
            attributed.append(off)  # the loop IS the cause; explaining it by itself is circular
        elif off.p95 is None:
            attributed.append(off)  # nothing to compare the stall against
        elif loop_worst_seconds < off.p95:
            attributed.append(off)  # the stall is too short to account for this percentile
        else:
            attributed.append(replace(off, explained_by_loop_stall_seconds=loop_worst_seconds))
    return attributed


__all__ = [
    "SpikeHealthOffender",
    "SpikeHealthVerdict",
    "evaluate_spike_health",
]
