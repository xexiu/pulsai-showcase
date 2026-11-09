"""
RED tests for the per-endpoint duration tracker (Finding K).

Contract — mirrors `db_metrics` / `redis_metrics`:

* `observe_endpoint_duration_seconds(route, duration_seconds)` records into a
  time-windowed deque and a Prometheus histogram. No-op when prometheus_client
  is missing.
* Warm-up grace shared with db/redis (first 5s of process suppressed).
* `get_endpoint_compact_health_view()` returns `{windows, primary_window,
  by_label: {window: {route: {count, p50, p95, p99, status}}}}`.
* Cardinality bound: only routes from `_TRACKED_ROUTES` (or `OTHER`) are
  observed. Anything else collapses to `OTHER` to prevent metric label
  explosion (per-user-id paths, ad-hoc URLs, etc.).
* Status is derived from p95 against `EndpointCompactThresholds` (warn/critical
  per-route or global default).
"""

from __future__ import annotations

import pytest

from src.infrastructure.observability import endpoint_metrics
from src.infrastructure.observability.endpoint_metrics import (
    _classify_endpoint,
    get_endpoint_compact_health_view,
    reset_unlabelled_endpoint_routes_for_tests,
    unlabelled_endpoint_routes,
)
from src.shared.constants.observability_metrics import TRACKED_ENDPOINTS
from src.shared.utils.datetime_utils import utc_now


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint_metrics._endpoint_window_state = endpoint_metrics._EndpointWindowState()
    monkeypatch.setattr(endpoint_metrics, "_warmup_grace_seconds", lambda: 0.0)


class TestClassifyEndpointRoute:
    """Cardinality guard: unknown routes collapse to OTHER."""

    def test_tracked_route_passes_through(self) -> None:
        sample = "/api/v1/market/chart-indicators"
        assert sample in TRACKED_ENDPOINTS
        assert endpoint_metrics._classify_endpoint(sample) == sample

    def test_unknown_route_collapses_to_other(self) -> None:
        assert endpoint_metrics._classify_endpoint("/api/v1/foo/bar/random") == "OTHER"

    def test_empty_route_returns_other(self) -> None:
        assert endpoint_metrics._classify_endpoint("") == "OTHER"

    def test_cardinality_is_bounded(self) -> None:
        """Allowed label values are the curated set + OTHER."""
        allowed = set(TRACKED_ENDPOINTS) | {"OTHER"}
        samples = [*TRACKED_ENDPOINTS, "/random/path", "/api/v1/users/abc-uuid-xyz", ""]
        observed = {endpoint_metrics._classify_endpoint(s) for s in samples}
        assert observed.issubset(allowed)


class TestObserveEndpointDurationSeconds:
    def test_appends_to_window_state(self) -> None:
        endpoint_metrics.observe_endpoint_duration_seconds("/api/v1/market/chart-indicators", 0.05)
        obs = endpoint_metrics._endpoint_window_state.observations
        assert len(obs) == 1
        assert obs[0].route == "/api/v1/market/chart-indicators"
        assert obs[0].value == 0.05

    def test_negative_duration_clamped_to_zero(self) -> None:
        endpoint_metrics.observe_endpoint_duration_seconds("/api/v1/market/chart-indicators", -1.0)
        assert endpoint_metrics._endpoint_window_state.observations[0].value == 0.0

    def test_no_op_when_prometheus_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "prometheus_client":
                raise ImportError
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        endpoint_metrics.observe_endpoint_duration_seconds("/api/v1/market/chart-indicators", 0.01)
        assert len(endpoint_metrics._endpoint_window_state.observations) == 1


class TestGetEndpointCompactHealthView:
    def test_returns_windows_and_by_label_structure(self) -> None:
        now = utc_now()
        for v in (0.05, 0.1, 0.5):
            endpoint_metrics._endpoint_window_state.observations.append(
                endpoint_metrics._TimedEndpointValue(
                    at=now,
                    route="/api/v1/market/chart-indicators",
                    value=v,
                )
            )
        view = endpoint_metrics.get_endpoint_compact_health_view(now=now)
        assert "windows" in view
        assert "primary_window" in view
        assert "by_label" in view
        primary = view["primary_window"]
        cell = view["by_label"][primary]["/api/v1/market/chart-indicators"]
        assert cell["count"] == 3
        assert cell["p95"] is not None
        assert cell["status"] in {"ok", "warn", "critical", "unknown"}

    def test_status_critical_when_p95_exceeds_threshold(self) -> None:
        now = utc_now()
        # 3 samples at 2 seconds — well above any reasonable p95 budget
        for _ in range(3):
            endpoint_metrics._endpoint_window_state.observations.append(
                endpoint_metrics._TimedEndpointValue(
                    at=now,
                    route="/api/v1/market/chart-indicators",
                    value=2.0,
                )
            )
        view = endpoint_metrics.get_endpoint_compact_health_view(now=now)
        primary = view["primary_window"]
        cell = view["by_label"][primary]["/api/v1/market/chart-indicators"]
        assert cell["status"] == "critical"

    def test_empty_cell_returns_unknown(self) -> None:
        view = endpoint_metrics.get_endpoint_compact_health_view()
        primary = view["primary_window"]
        # A tracked endpoint with no samples → status unknown, count 0
        cell = view["by_label"][primary][next(iter(TRACKED_ENDPOINTS))]
        assert cell["count"] == 0
        assert cell["status"] == "unknown"
        assert cell["p95"] is None


class TestLongRunningRoutesStayMeasured:
    """Excluded-from-OTHER must not mean excluded-from-EVERYTHING.

    057fa36fb dropped the observation entirely for backtest routes, so a route degrading
    from 5 s to 300 s produced no signal anywhere. They now land in their own bucket with
    their own thresholds: out of OTHER, still visible.
    """

    def test_long_running_route_is_classified_to_its_own_bucket(self) -> None:
        from src.shared.constants.observability_metrics import LONG_RUNNING_LABEL

        assert endpoint_metrics._classify_endpoint("/api/v1/backtest/run") == LONG_RUNNING_LABEL

    def test_long_running_duration_is_still_recorded(self) -> None:
        from src.shared.constants.observability_metrics import LONG_RUNNING_LABEL

        endpoint_metrics.observe_endpoint_duration_seconds(endpoint_metrics._classify_endpoint("/api/v1/backtest/run"), 45.0)

        recorded = [o for o in endpoint_metrics._endpoint_window_state.observations if o.route == LONG_RUNNING_LABEL]
        assert len(recorded) == 1
        assert recorded[0].value == 45.0

    def test_long_running_does_not_pollute_other_bucket(self) -> None:
        from src.shared.constants.observability_metrics import OTHER_LABEL

        endpoint_metrics.observe_endpoint_duration_seconds(endpoint_metrics._classify_endpoint("/api/v1/backtest/run"), 300.0)

        other = [o for o in endpoint_metrics._endpoint_window_state.observations if o.route == OTHER_LABEL]
        assert other == []

    def test_long_running_is_judged_on_its_own_threshold(self) -> None:
        """A 45 s backtest is fine; the interactive threshold would have paged CRITICAL."""
        from src.shared.constants.observability_metrics import (
            ENDPOINT_LONG_RUNNING_P95_CRITICAL_SECONDS,
            LONG_RUNNING_LABEL,
        )

        warn, critical = endpoint_metrics._thresholds_for(LONG_RUNNING_LABEL, endpoint_metrics.EndpointCompactThresholds())

        assert critical == ENDPOINT_LONG_RUNNING_P95_CRITICAL_SECONDS
        assert warn < critical


class TestEndpointSpikeExcludedPaths:
    """Long-running batch routes must not poison OTHER spike percentiles."""

    def test_backtest_run_excluded(self) -> None:
        assert endpoint_metrics.is_endpoint_spike_excluded("/api/v1/backtest/run") is True

    def test_backtest_hub_optimize_excluded(self) -> None:
        assert endpoint_metrics.is_endpoint_spike_excluded("/api/v1/backtest-hub/optimize") is True

    def test_chart_indicators_not_excluded(self) -> None:
        assert endpoint_metrics.is_endpoint_spike_excluded("/api/v1/market/chart-indicators") is False

    def test_backtest_prefix_does_not_exclude_unrelated(self) -> None:
        assert endpoint_metrics.is_endpoint_spike_excluded("/api/v1/market/ohlcv") is False


# REUSE-AUDIT: considered apps/api/tests/unit/infrastructure/observability/test_endpoint_metrics.py
# and this IS that file -- appended, reusing its imports. Considered
# apps/api/src/infrastructure/observability/endpoint_metrics.py -- EXTENDED following the
# `synthetic_samples_dropped` precedent already in it, and mirroring the identical change made to
# redis_metrics.py the same day, rather than inventing a third shape for one idea.


class TestTheOtherBucketNamesWhatItSaw:
    """OTHER went CRITICAL in prod and could not say which routes it was.

    MEASURED 2026-09-06 while the owner reported a page on every dashboard load:

        endpoint OTHER  n=16  p50 1.147s  p95 2.468s  CRITICAL

    Sixteen requests averaging over a second, and nothing to say which routes they were:
    TRACKED_ENDPOINTS names eight, and the entire rest of the application collapses into one
    bucket that can page while naming nothing.

    The identical change to `redis_metrics` the same day proved the value inside ten minutes --
    prod answered `['GETDEL']`, a command the client had always issued and the labelled set had
    never covered. Guessing first had cost real time there, and would here.

    SAFE because the middleware resolves `request.scope["route"].path` -- the TEMPLATE,
    `/items/{id}` -- precisely so per-UUID labels cannot happen. These carry no ids, and they
    never become Prometheus labels.
    """

    def setup_method(self) -> None:
        reset_unlabelled_endpoint_routes_for_tests()

    def test_an_untracked_route_is_remembered(self) -> None:
        _classify_endpoint("/api/v1/portfolio/performance")

        assert "/api/v1/portfolio/performance" in unlabelled_endpoint_routes()

    def test_a_tracked_route_is_not_recorded(self) -> None:
        """Only the bucket that cannot explain itself needs explaining."""
        for route in TRACKED_ENDPOINTS:
            _classify_endpoint(route)

        assert unlabelled_endpoint_routes() == ()

    def test_a_long_running_route_is_not_recorded_as_unlabelled(self) -> None:
        """LONG_RUNNING is a deliberate bucket with its own band, not an unknown."""
        _classify_endpoint("/api/v1/backtest/run")

        assert unlabelled_endpoint_routes() == ()

    def test_the_same_route_is_recorded_once(self) -> None:
        for _ in range(5):
            _classify_endpoint("/api/v1/portfolio/performance")

        assert unlabelled_endpoint_routes().count("/api/v1/portfolio/performance") == 1

    def test_it_is_bounded_by_the_size_of_the_tracked_set(self) -> None:
        for index in range(len(TRACKED_ENDPOINTS) * 3):
            _classify_endpoint(f"/api/v1/unknown/{index}")

        assert len(unlabelled_endpoint_routes()) <= len(TRACKED_ENDPOINTS)

    def test_the_view_publishes_them(self) -> None:
        """Recorded and never published is the inert-value defect this repo has shipped twice."""
        _classify_endpoint("/api/v1/portfolio/performance")

        view = get_endpoint_compact_health_view()

        assert "/api/v1/portfolio/performance" in view["other_routes_seen"]

    def test_the_view_publishes_an_empty_list_when_nothing_was_unlabelled(self) -> None:
        assert get_endpoint_compact_health_view()["other_routes_seen"] == []
