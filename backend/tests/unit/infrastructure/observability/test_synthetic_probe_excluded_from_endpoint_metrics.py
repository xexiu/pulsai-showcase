"""My own monitoring must not manufacture the page it is watching for.

MEASURED ON PROD, 2026-09-06, from the live compact view:

    "/api/v1/market/chart-indicators": count 1,  p50 = p95 = p99 = 0.2148
    "OTHER":                           count 2,  p95 = 0.326

Organic traffic on these routes is ONE OR TWO requests per 5-minute window, so a "p95" is
the single slowest request in it. The alert floor (DEFAULT_SPIKE_ALERT_MIN_SAMPLES = 20,
and no SPIKE_* override is set on the prod service) correctly discards windows that thin.

Which means a recorded `endpoint/OTHER` offender REQUIRES >= 20 samples in five minutes --
something organic traffic at that hour cannot produce. My 63-endpoint sweep produces it in
about a minute, and supplies the slow uncached first-hit latencies at the same time. So the
sweep both clears the floor and sets the percentile: 8 pages in 72h, every one inside a
window I was probing, against 18 consecutive hours of zero degraded ticks when I was not.

THE FIX is the one this module already uses twice for the same reason -- do not let
unrepresentative samples into the percentile. `_EXCLUDED_PATHS` drops /docs and /metrics;
`observe_endpoint_duration_seconds` drops everything inside the warm-up grace. A synthetic
probe is that same category, so it is dropped at the middleware rather than filtered later.

THE HONESTY CLAUSE (ARCHITECTURE_PATTERNS section 5): an exclusion that cannot be seen is
how a real regression hides. If probe traffic were silently discarded and the probe were the
only traffic, the view would read "no data" identically to a healthy idle system. So the
drop is COUNTED and the count is published in the compact view.

REUSE-AUDIT: considered ENDPOINT_SPIKE_EXCLUDED_PATH_PREFIXES (excludes by ROUTE -- wrong
axis here, since the probe hits the same routes real users do), and the warm-up grace
(excludes by TIME since boot, also the wrong axis). Neither can express "this caller is not
a user". No existing helper reads the User-Agent.
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.testclient import TestClient

from src.infrastructure.observability.endpoint_metrics import (
    get_endpoint_compact_health_view,
    install_endpoint_metrics_middleware,
    is_synthetic_probe_user_agent,
    reset_synthetic_samples_dropped_for_tests,
    synthetic_samples_dropped,
)
from src.shared.constants.observability_metrics import SYNTHETIC_PROBE_USER_AGENT_TOKEN


class TestItRecognisesTheProbe:
    def test_the_exact_token_is_recognised(self) -> None:
        assert is_synthetic_probe_user_agent(SYNTHETIC_PROBE_USER_AGENT_TOKEN) is True

    def test_it_matches_inside_a_longer_user_agent(self) -> None:
        """Probes carry a realistic UA so they exercise the same code path a browser does."""
        ua = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) {SYNTHETIC_PROBE_USER_AGENT_TOKEN}"

        assert is_synthetic_probe_user_agent(ua) is True

    def test_the_match_is_case_insensitive(self) -> None:
        assert is_synthetic_probe_user_agent(SYNTHETIC_PROBE_USER_AGENT_TOKEN.upper()) is True


class TestItLeavesRealTrafficAlone:
    """A false positive here silently blinds the metric for real users -- the worse failure."""

    def test_a_browser_is_not_a_probe(self) -> None:
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

        assert is_synthetic_probe_user_agent(ua) is False

    def test_a_missing_user_agent_is_not_a_probe(self) -> None:
        """Absent UA is an ordinary client, and treating it as synthetic would hide real load."""
        assert is_synthetic_probe_user_agent(None) is False

    def test_an_empty_user_agent_is_not_a_probe(self) -> None:
        assert is_synthetic_probe_user_agent("") is False

    def test_an_unrelated_bot_is_not_a_probe(self) -> None:
        """Only OUR probe is excluded. A crawler's latency is real latency somebody served."""
        assert is_synthetic_probe_user_agent("Googlebot/2.1 (+http://www.google.com/bot.html)") is False


class TestTheTokenIsSpecificEnoughToBeSafe:
    def test_the_token_is_not_a_substring_of_common_user_agents(self) -> None:
        """A token like 'python' or 'curl' would exclude real integrations by accident."""
        common = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Version/17.0 Mobile Safari/604.1",
            "python-requests/2.31.0",
            "curl/8.4.0",
            "PostmanRuntime/7.36.0",
            "node-fetch/1.0",
        )

        for ua in common:
            assert is_synthetic_probe_user_agent(ua) is False, f"token collides with {ua!r}"


def _app_with_metrics() -> FastAPI:
    app = FastAPI()

    @app.get("/probed")
    async def probed() -> dict[str, str]:
        return {"ok": "yes"}

    install_endpoint_metrics_middleware(app)
    return app


class TestTheMiddlewareActuallyDropsIt:
    """The predicate being right proves nothing if the middleware never calls it."""

    def setup_method(self) -> None:
        reset_synthetic_samples_dropped_for_tests()

    def test_a_probe_request_is_counted_as_dropped(self) -> None:
        client = TestClient(_app_with_metrics())

        before = synthetic_samples_dropped()
        response = client.get("/probed", headers={"User-Agent": SYNTHETIC_PROBE_USER_AGENT_TOKEN})

        assert response.status_code == 200, "the request must still be SERVED, only unmeasured"
        assert synthetic_samples_dropped() == before + 1

    def test_a_normal_request_is_not_counted_as_dropped(self) -> None:
        client = TestClient(_app_with_metrics())

        before = synthetic_samples_dropped()
        client.get("/probed", headers={"User-Agent": "Mozilla/5.0 Chrome/120"})

        assert synthetic_samples_dropped() == before

    def test_the_drop_count_is_published_in_the_compact_view(self) -> None:
        """The honesty clause: an exclusion nobody can see is how a regression hides."""
        client = TestClient(_app_with_metrics())
        client.get("/probed", headers={"User-Agent": SYNTHETIC_PROBE_USER_AGENT_TOKEN})

        view = get_endpoint_compact_health_view()

        assert view["synthetic_samples_dropped"] >= 1

    def test_the_view_still_carries_what_the_evaluator_reads(self) -> None:
        """Adding a key must not disturb evaluate_spike_health's contract."""
        view = get_endpoint_compact_health_view()

        assert "primary_window" in view
        assert "by_label" in view
        assert view["primary_window"] in view["by_label"]
