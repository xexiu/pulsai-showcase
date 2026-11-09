"""Per-endpoint HTTP latency histogram + compact percentile view (Finding K).

Mirrors the pattern in `db_metrics` / `redis_metrics`. In-process Prometheus
histogram plus a time-windowed deque used for the admin compact view.

SECURITY / COST: only routes listed in `TRACKED_ENDPOINTS` get their own
label value. Every other request collapses to label `OTHER`. This keeps
Prometheus series cardinality bounded — adding a per-user-id or per-trade-id
path would otherwise explode the label space.

WIRE POINT: `install_endpoint_metrics_middleware(app)` registers a thin ASGI
middleware that measures wall-clock per-request duration. The middleware is
installed unconditionally at API boot (it is NOT gated on OTEL — OTEL is the
optional remote export path; this is the local in-process path).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import timedelta
from time import monotonic, perf_counter
from typing import TYPE_CHECKING, Any

from src.infrastructure.observability._compact_view_helpers import (
    compute_percentiles,
    compute_threshold_status,
    trim_old_observations,
)
from src.infrastructure.observability.request_query_count import (
    finish_request_query_count,
    start_request_query_count,
)
from src.infrastructure.observability.synthetic_probe_context import (
    mark_current_request_synthetic,
    reset_current_request_synthetic,
)
from src.shared.constants.observability_metrics import (
    DB_QUERIES_PER_REQUEST_WARN,
    ENDPOINT_DURATION_HISTOGRAM_BUCKETS_SECONDS,
    ENDPOINT_LONG_RUNNING_P95_CRITICAL_SECONDS,
    ENDPOINT_LONG_RUNNING_P95_WARN_SECONDS,
    ENDPOINT_P95_CRITICAL_SECONDS,
    ENDPOINT_P95_WARN_SECONDS,
    ENDPOINT_SPIKE_EXCLUDED_PATH_PREFIXES,
    LONG_RUNNING_LABEL,
    OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES,
    OTHER_LABEL,
    SYNTHETIC_PROBE_USER_AGENT_TOKEN,
    TRACKED_ENDPOINTS,
    WARMUP_GRACE_ENV_VAR,
    WARMUP_GRACE_SECONDS,
)
from src.shared.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from fastapi import FastAPI
    from starlette.requests import Request

logger = logging.getLogger(__name__)

_PROCESS_START_PERF = perf_counter()


def _seconds_since_process_start() -> float:
    return perf_counter() - _PROCESS_START_PERF


def _warmup_grace_seconds() -> float:
    import os

    raw = os.environ.get(WARMUP_GRACE_ENV_VAR, "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return WARMUP_GRACE_SECONDS


_endpoint_lock = threading.Lock()
_endpoint_duration_histogram: Any = None
_TRACKED_SET = set(TRACKED_ENDPOINTS)


@dataclass
class _TimedEndpointValue:
    at: Any
    route: str
    value: float


@dataclass
class _EndpointWindowState:
    observations: list[_TimedEndpointValue] = field(default_factory=list)


_endpoint_window_state = _EndpointWindowState()

#: How many requests were dropped from the percentiles for identifying as synthetic monitoring.
#:
#: Published in the compact view so the exclusion is VISIBLE. Without it, "the prober is the only
#: traffic" and "healthy and idle" render identically as an empty window, and a real regression
#: could hide behind an exclusion nobody can see (ARCHITECTURE_PATTERNS section 5).
_synthetic_samples_dropped: int = 0


def _note_synthetic_sample_dropped() -> None:
    global _synthetic_samples_dropped
    with _endpoint_lock:
        _synthetic_samples_dropped += 1


def synthetic_samples_dropped() -> int:
    """Total requests excluded as synthetic monitoring since process start."""
    with _endpoint_lock:
        return _synthetic_samples_dropped


def reset_synthetic_samples_dropped_for_tests() -> None:
    """Clear the drop counter (unit tests only)."""
    global _synthetic_samples_dropped
    with _endpoint_lock:
        _synthetic_samples_dropped = 0


@dataclass(frozen=True)
class EndpointCompactThresholds:
    """p95 thresholds for status badges. SoT for SLO bands."""

    warn_seconds: float = ENDPOINT_P95_WARN_SECONDS
    critical_seconds: float = ENDPOINT_P95_CRITICAL_SECONDS


def _trim_old(now: Any) -> None:
    _endpoint_window_state.observations = trim_old_observations(_endpoint_window_state.observations, now)


#: The route TEMPLATES that landed in OTHER, so the bucket can explain itself.
#:
#: MEASURED on prod 2026-09-06, while the owner reported a page on every dashboard load:
#: `endpoint OTHER n=16 p50 1.147s p95 2.468s CRITICAL`. Sixteen requests averaging over a second
#: with no way to know which routes they were -- `TRACKED_ENDPOINTS` names eight, and everything
#: else in the application collapses into one bucket that can go critical while naming nothing.
#:
#: The same treatment fixed the sibling bucket the same day: `redis OTHER` was equally opaque, and
#: within ten minutes of publishing the names prod answered `['GETDEL']` -- a command the client
#: had always issued and the labelled set had never covered. Guessing first had cost real time.
#:
#: SAFE TO RECORD because the middleware already resolves `request.scope["route"].path` -- the
#: TEMPLATE, `/items/{id}` -- specifically so that per-UUID labels cannot happen. So these carry
#: no ids and no user data. They never become Prometheus labels either, which is what the
#: cardinality guard in this module protects; this is a bounded diagnostic field beside
#: `synthetic_samples_dropped`.
_unlabelled_routes: set[str] = set()

#: DERIVED, not picked: never remember more unlabelled routes than there are tracked ones.
_UNLABELLED_ROUTE_CAPACITY = len(TRACKED_ENDPOINTS)


def unlabelled_endpoint_routes() -> tuple[str, ...]:
    """Distinct route templates that fell into OTHER, sorted for a stable read."""
    with _endpoint_lock:
        return tuple(sorted(_unlabelled_routes))


def reset_unlabelled_endpoint_routes_for_tests() -> None:
    """Forget the recorded OTHER route templates (unit tests only)."""
    with _endpoint_lock:
        _unlabelled_routes.clear()


def _classify_endpoint(route: str) -> str:
    """Collapse unknown routes to OTHER, remembering which ones. Cardinality guard for labels."""
    if not route:
        return OTHER_LABEL
    if is_endpoint_spike_excluded(route):
        return LONG_RUNNING_LABEL
    if route in _TRACKED_SET:
        return route
    with _endpoint_lock:
        if len(_unlabelled_routes) < _UNLABELLED_ROUTE_CAPACITY:
            _unlabelled_routes.add(route)
    return OTHER_LABEL


def is_endpoint_spike_excluded(route: str) -> bool:
    """True when *route* is a known long-running batch path (skip spike percentiles)."""
    if not route:
        return False
    return any(route == prefix or route.startswith(f"{prefix}/") for prefix in ENDPOINT_SPIKE_EXCLUDED_PATH_PREFIXES)


def is_synthetic_probe_user_agent(user_agent: str | None) -> bool:
    """True when the caller identified itself as synthetic monitoring, not a user.

    Its latency is real, but it is not USER latency, and mixing the two corrupts the
    percentiles that page a human -- see SYNTHETIC_PROBE_USER_AGENT_TOKEN for the measurement
    that made this necessary. A missing or empty User-Agent is an ordinary client: treating
    it as synthetic would blind the metric for exactly the callers least able to say so.
    """
    if not user_agent:
        return False
    return SYNTHETIC_PROBE_USER_AGENT_TOKEN.casefold() in user_agent.casefold()


#: Monotonic time of the last REAL request per route TEMPLATE. The warmup registry reads it so a
#: warmer refreshes only while someone uses what it warms (`WarmupRegistry._due`). Synthetic probes,
#: the excluded doc/metrics paths and unmatched URLs never count -- the last keeps the dict bounded
#: by the app's declared routes, whatever a scanner sends.
_last_real_request_at: dict[str, float] = {}


def note_real_request(route: str, *, at: float | None = None) -> None:
    """Record that a real client was just served on ``route`` (a route template, never a raw URL)."""
    stamp = monotonic() if at is None else at
    with _endpoint_lock:
        _last_real_request_at[route] = stamp


def seconds_since_real_request(routes: Iterable[str], *, now: float | None = None) -> float | None:
    """Seconds since the newest real request to any of ``routes``; None when none was ever served."""
    with _endpoint_lock:
        stamps = [_last_real_request_at[route] for route in routes if route in _last_real_request_at]
    if not stamps:
        return None
    return (monotonic() if now is None else now) - max(stamps)


def observe_endpoint_duration_seconds(route: str, duration_seconds: float) -> None:
    """Record one HTTP request's wall-clock duration.

    Dropped during warm-up grace (excludes pool warm-up taint, Finding E).
    """
    if _seconds_since_process_start() < _warmup_grace_seconds():
        return
    if duration_seconds < 0:
        duration_seconds = 0.0

    with _endpoint_lock:
        now = utc_now()
        _endpoint_window_state.observations.append(_TimedEndpointValue(at=now, route=route, value=duration_seconds))
        _trim_old(now)

    global _endpoint_duration_histogram
    try:
        from prometheus_client import Histogram
    except ImportError:
        return

    with _endpoint_lock:
        if _endpoint_duration_histogram is None:
            _endpoint_duration_histogram = Histogram(
                "pulsai_api_endpoint_duration_seconds",
                "HTTP request duration grouped by tracked endpoint.",
                labelnames=("route",),
                buckets=ENDPOINT_DURATION_HISTOGRAM_BUCKETS_SECONDS,
            )
    _endpoint_duration_histogram.labels(route=route).observe(duration_seconds)


def _thresholds_for(route: str, th: EndpointCompactThresholds) -> tuple[float, float]:
    """Per-bucket p95 thresholds: long-running routes are judged on their own scale.

    Without this the LONG_RUNNING bucket would be measured against the interactive
    thresholds and page CRITICAL constantly, which is what motivated dropping those routes
    from the metrics entirely — the cure that created the blind spot.
    """
    if route == LONG_RUNNING_LABEL:
        return ENDPOINT_LONG_RUNNING_P95_WARN_SECONDS, ENDPOINT_LONG_RUNNING_P95_CRITICAL_SECONDS
    return th.warn_seconds, th.critical_seconds


def get_endpoint_compact_health_view(
    *,
    now: Any | None = None,
    metric_windows: tuple[tuple[str, int], ...] | None = None,
    thresholds: EndpointCompactThresholds | None = None,
) -> dict[str, Any]:
    """Per-route p50/p95/p99/count by window, with status from p95."""
    window_minutes: dict[str, int] = dict(metric_windows or OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES)
    now_dt = utc_now() if now is None else now
    th = thresholds or EndpointCompactThresholds()

    with _endpoint_lock:
        _trim_old(now_dt)
        snapshot = list(_endpoint_window_state.observations)

    routes = (*TRACKED_ENDPOINTS, OTHER_LABEL, LONG_RUNNING_LABEL)
    by_label: dict[str, dict[str, dict[str, Any]]] = {}
    for window_key, minutes in window_minutes.items():
        floor = now_dt - timedelta(minutes=minutes)
        by_route: dict[str, dict[str, Any]] = {}
        for route in routes:
            values = [o.value for o in snapshot if o.at >= floor and o.route == route]
            percentiles = compute_percentiles(values)
            warn_seconds, critical_seconds = _thresholds_for(route, th)
            by_route[route] = {
                "count": len(values),
                **percentiles,
                "status": compute_threshold_status(
                    percentiles["p95"],
                    warn=warn_seconds,
                    critical=critical_seconds,
                ),
            }
        by_label[window_key] = by_route

    primary_window_key = next(iter(window_minutes.keys()))
    return {
        "windows": list(window_minutes.keys()),
        "primary_window": primary_window_key,
        "by_label": by_label,
        # The exclusion, made visible. `evaluate_spike_health` reads only `primary_window` and
        # `by_label`, so this is inert for alerting and purely for the human reading the admin
        # view -- which is the point: an empty window next to a large drop count says "the
        # prober is the only traffic", and next to zero it says "genuinely idle".
        "synthetic_samples_dropped": synthetic_samples_dropped(),
        # WHAT LANDED IN OTHER. That bucket went critical on prod at p50 1.147s over 16 samples
        # and could name nothing; route TEMPLATES carry no ids, so publishing them turns a page
        # nobody can act on into one that points somewhere.
        "other_routes_seen": list(unlabelled_endpoint_routes()),
    }


# ---------------------------------------------------------------------------
# Middleware: timing every request, classifying the route, recording.
# ---------------------------------------------------------------------------

_MIDDLEWARE_INSTALLED_ATTR = "_pulsai_endpoint_metrics_installed"

# Excluded paths: same as OTEL middleware — /metrics scrape + docs noise.
_EXCLUDED_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/metrics"})


def install_endpoint_metrics_middleware(app: FastAPI) -> None:
    """Register the per-request timing middleware (idempotent per-app)."""
    if getattr(app, _MIDDLEWARE_INSTALLED_ATTR, False):
        return

    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Any]],
    ) -> Any:
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        # SYNTHETIC MONITORING IS NOT A USER. The agent's health sweep hits ~63 endpoints in
        # about a minute; organic traffic on the same routes is 1-2 requests per 5-minute
        # window. That burst clears the 20-sample alert floor which organic traffic cannot,
        # and fills it with cold-path latencies, so the sweep manufactures the very page it
        # exists to watch for. Counted rather than silently dropped: an invisible exclusion
        # would make "the prober is the only traffic" indistinguishable from "healthy and
        # idle" (ARCHITECTURE_PATTERNS section 5, the honesty clause).
        # HALF A FIX, corrected 2026-09-06. Returning here stopped probe traffic skewing the
        # ENDPOINT percentiles and nothing else -- but an AUTHENTICATED probe still INSERTs and
        # still reads Redis, and those samples page from the `db` and `redis` views on their
        # own thresholds. The owner was paged three more times, and every offender named was
        # `db INSERT` or `redis GET`, never the endpoint. A guest 401s before touching either,
        # which is exactly why he only saw it while the probe was logged in.
        #
        # So the flag is published to the whole request context, not just consumed here.
        if is_synthetic_probe_user_agent(request.headers.get("user-agent")):
            _note_synthetic_sample_dropped()
            token = mark_current_request_synthetic()
            try:
                return await call_next(request)
            finally:
                # A ContextVar is NOT request-scoped by itself -- the same task serves the next
                # request. An unreset token would mark real traffic synthetic and hide genuine
                # degradation, which is worse than the noise being removed.
                reset_current_request_synthetic(token)

        # Prefer the route template ("/items/{id}") over the literal URL so
        # `application_name=pulsai` doesn't see one label per UUID. FastAPI
        # exposes the matched route on request.scope["route"].
        route_obj = request.scope.get("route")
        route_path = getattr(route_obj, "path", None) or request.url.path

        start = perf_counter()
        query_token = start_request_query_count()
        try:
            response = await call_next(request)
        finally:
            queries = finish_request_query_count(query_token)
        elapsed = perf_counter() - start
        observe_endpoint_duration_seconds(_classify_endpoint(route_path), elapsed)
        # Read AFTER the call: routing writes the matched route into this same scope. No route means
        # no match (a 404) -- not demand for anything a warmer could keep warm.
        matched = getattr(request.scope.get("route"), "path", None)
        if matched:
            note_real_request(matched)
        if queries > DB_QUERIES_PER_REQUEST_WARN:
            logger.warning("db_queries_per_request", extra={"route": matched or route_path, "queries": queries})
        return response

    app.middleware("http")(middleware)
    setattr(app, _MIDDLEWARE_INSTALLED_ATTR, True)


__all__ = [
    "EndpointCompactThresholds",
    "get_endpoint_compact_health_view",
    "install_endpoint_metrics_middleware",
    "is_endpoint_spike_excluded",
    "is_synthetic_probe_user_agent",
    "observe_endpoint_duration_seconds",
    "reset_synthetic_samples_dropped_for_tests",
    "synthetic_samples_dropped",
]
