"""A probe that authenticates does real DB and Redis work, and it must not page the owner.

OWNER, 2026-09-06, after three further pages while the agent measured prod:
*"every time you auth and test, the spikes happens (not when your guest) :S on /dashboard and
full chart!"*

He is describing the exact shape of a half-finished fix. That morning's exclusion
(`is_synthetic_probe_user_agent`) was wired into the HTTP middleware and NOWHERE else, so probe
traffic stopped skewing the ENDPOINT percentiles and kept skewing everything underneath. The
pages that followed prove it - every offender named was a different source:

    db INSERT    [5m] critical p95=0.208s
    db INSERT    [5m] critical p95=0.253s
    redis GET    [5m] critical p95=0.462s
    redis EXISTS [5m] critical p95=0.235s

and never the endpoint. A GUEST request 401s before it touches the database or Redis, which is
precisely why the owner only ever saw this while the probe was logged in.

WHY A CONTEXTVAR IS THE SEAM. The user-agent is known at one point (the middleware) and needed
at several points far below it - a SQLAlchemy event listener and a Redis command wrapper,
neither of which can see a request. The contextvar carries it, and is inherited by tasks the
request spawns, which is right: work a probe caused is still work a probe caused.
"""

from __future__ import annotations

import asyncio

import pytest

from src.infrastructure.observability.db_metrics import (
    get_db_compact_health_view,
    observe_db_query_duration_seconds,
    reset_synthetic_db_samples_dropped_for_tests,
    synthetic_db_samples_dropped,
)
from src.infrastructure.observability.redis_metrics import (
    get_redis_compact_health_view,
    observe_redis_op_duration_seconds,
    reset_synthetic_redis_samples_dropped_for_tests,
    synthetic_redis_samples_dropped,
)
from src.infrastructure.observability.synthetic_probe_context import (
    is_current_request_synthetic,
    mark_current_request_synthetic,
    reset_current_request_synthetic,
)


@pytest.fixture(autouse=True)
def _no_warmup_grace_and_clean_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both sinks drop everything during the post-boot grace window; neutralise it.

    Without this the tests would pass for the WRONG reason - every observation dropped by the
    warm-up guard rather than by the synthetic guard under test.
    """
    monkeypatch.setattr("src.infrastructure.observability.db_metrics._warmup_grace_seconds", lambda: 0.0)
    monkeypatch.setattr("src.infrastructure.observability.redis_metrics._warmup_grace_seconds", lambda: 0.0)
    from src.infrastructure.observability import db_metrics, redis_metrics

    db_metrics._db_window_state.observations.clear()
    redis_metrics._redis_window_state.observations.clear()
    reset_synthetic_db_samples_dropped_for_tests()
    reset_synthetic_redis_samples_dropped_for_tests()


def _db_sample_count() -> int:
    view = get_db_compact_health_view()
    window = view["by_label"].get(view["primary_window"], {})
    return sum(int(entry.get("count", 0)) for entry in window.values())


def _redis_sample_count() -> int:
    view = get_redis_compact_health_view()
    window = view["by_label"].get(view["primary_window"], {})
    return sum(int(entry.get("count", 0)) for entry in window.values())


class TestTheMarkerItself:
    def test_work_with_no_request_context_is_real(self) -> None:
        """Celery tasks, warmers and the watcher itself have no request - they must count.

        Defaulting the other way would silently erase every background sample, which is a worse
        failure than the noise being removed.
        """
        assert is_current_request_synthetic() is False

    def test_mark_then_reset_restores_the_previous_value(self) -> None:
        """An unreset token marks REAL traffic synthetic and hides genuine degradation."""
        token = mark_current_request_synthetic()
        assert is_current_request_synthetic() is True

        reset_current_request_synthetic(token)

        assert is_current_request_synthetic() is False

    async def test_a_task_the_request_spawns_inherits_the_flag(self) -> None:
        """THE LOAD-BEARING PROPERTY. The DB and Redis work happens below the middleware.

        A detached cache fill or a gathered fan-out started by a probe request is still work the
        probe caused, and contextvars are what carry that across the await boundary.
        """
        seen: list[bool] = []

        async def _child() -> None:
            seen.append(is_current_request_synthetic())

        token = mark_current_request_synthetic()
        try:
            await asyncio.gather(_child(), _child())
        finally:
            reset_current_request_synthetic(token)

        assert seen == [True, True]


class TestDbObservationsFromAProbe:
    def test_real_traffic_is_still_recorded(self) -> None:
        observe_db_query_duration_seconds("INSERT", 0.2)

        assert _db_sample_count() == 1
        assert synthetic_db_samples_dropped() == 0

    def test_a_probe_insert_does_not_reach_the_percentiles(self) -> None:
        """THE DEFECT: `db INSERT critical p95=0.208s`, paged twice, caused by the agent."""
        token = mark_current_request_synthetic()
        try:
            observe_db_query_duration_seconds("INSERT", 0.9)
        finally:
            reset_current_request_synthetic(token)

        assert _db_sample_count() == 0

    def test_the_drop_is_counted_not_silent(self) -> None:
        """An invisible exclusion makes "only a prober is running" look like "healthy and idle"."""
        token = mark_current_request_synthetic()
        try:
            observe_db_query_duration_seconds("INSERT", 0.9)
            observe_db_query_duration_seconds("SELECT", 0.4)
        finally:
            reset_current_request_synthetic(token)

        assert synthetic_db_samples_dropped() == 2

    def test_real_traffic_during_the_same_window_still_pages(self) -> None:
        """The filter must remove the probe's samples ONLY, never the user's."""
        token = mark_current_request_synthetic()
        try:
            observe_db_query_duration_seconds("INSERT", 0.9)
        finally:
            reset_current_request_synthetic(token)
        observe_db_query_duration_seconds("INSERT", 0.3)

        assert _db_sample_count() == 1


class TestRedisObservationsFromAProbe:
    def test_real_traffic_is_still_recorded(self) -> None:
        observe_redis_op_duration_seconds("GET", 0.1)

        assert _redis_sample_count() == 1
        assert synthetic_redis_samples_dropped() == 0

    def test_a_probe_get_does_not_reach_the_percentiles(self) -> None:
        """THE DEFECT: `redis GET critical p95=0.462s`, while the endpoint view was already clean."""
        token = mark_current_request_synthetic()
        try:
            observe_redis_op_duration_seconds("GET", 0.5)
            observe_redis_op_duration_seconds("EXISTS", 0.25)
        finally:
            reset_current_request_synthetic(token)

        assert _redis_sample_count() == 0
        assert synthetic_redis_samples_dropped() == 2


class TestTheExclusionIsVISIBLE:
    """Counting a drop and never publishing it is the same as not counting it.

    THE DEFECT THIS PINS, and it is mine from the same day. The commit that added these
    counters claimed in its message that "both sinks publish a drop counter". They did not:
    the values were computed, stored, exposed through an accessor, and never placed in the
    compact view any human or alert actually reads. That is the inert-value shape this repo
    has shipped twice before (`spot_bh_final`, `combo_top_raw_incl_ruin`) -- computed and
    never written -- and the honesty clause the commit invoked was therefore unsatisfied.

    An accessor nobody calls is not publication. These tests assert the number reaches the
    VIEW, which is the only place it can do its job.
    """

    def test_the_db_view_publishes_the_drop_count(self) -> None:
        token = mark_current_request_synthetic()
        try:
            observe_db_query_duration_seconds("INSERT", 0.9)
        finally:
            reset_current_request_synthetic(token)

        assert get_db_compact_health_view()["synthetic_samples_dropped"] == 1

    def test_the_redis_view_publishes_the_drop_count(self) -> None:
        token = mark_current_request_synthetic()
        try:
            observe_redis_op_duration_seconds("GET", 0.5)
        finally:
            reset_current_request_synthetic(token)

        assert get_redis_compact_health_view()["synthetic_samples_dropped"] == 1

    def test_both_views_publish_zero_when_nothing_was_excluded(self) -> None:
        """An absent key and a zero are different: the field must always be present to read."""
        observe_db_query_duration_seconds("SELECT", 0.01)
        observe_redis_op_duration_seconds("GET", 0.01)

        assert get_db_compact_health_view()["synthetic_samples_dropped"] == 0
        assert get_redis_compact_health_view()["synthetic_samples_dropped"] == 0
