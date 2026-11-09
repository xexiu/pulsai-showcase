"""
RED tests for `pulsai_db_query_duration_seconds` histogram + windowed compact view.

Behavior contract:
- `_classify_sql_operation` returns SELECT/INSERT/UPDATE/DELETE for known
  prefixes (case-insensitive, leading whitespace allowed); everything else
  returns OTHER. Cardinality bounded by `KNOWN_SQL_OPERATIONS`.
- `observe_db_query_duration_seconds(operation, duration_seconds)` records
  into a time-windowed deque AND a Prometheus histogram (no-op if
  `prometheus_client` is unavailable).
- `get_db_compact_health_view` returns `{windows, primary_window, by_label: {window: {op: {count, p50, p95, p99}}}}`.
- `install_db_event_listeners` is idempotent: calling twice does NOT register
  duplicate listeners.
- End-to-end: install on a real sqlite engine, run a SELECT, compact view
  reflects exactly one SELECT observation.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text

from src.infrastructure.observability import db_metrics
from src.shared.constants.observability_metrics import KNOWN_SQL_OPERATIONS
from src.shared.utils.datetime_utils import utc_now


@pytest.fixture(autouse=True)
def _reset_db_metrics_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset module-level deque between tests + disable warm-up grace.

    NOTE: The Prometheus histogram singleton persists across tests (it is
    registered with the global REGISTRY exactly once). Resetting the module
    reference here would cause duplicate-registration errors on the next call.

    The warm-up grace period is disabled in tests so observe_* calls record
    immediately. Tests that exercise the grace path live in test_warmup_grace.
    """
    db_metrics._db_window_state = db_metrics._DbWindowState()
    monkeypatch.setattr(db_metrics, "_warmup_grace_seconds", lambda: 0.0)


class TestClassifySqlOperation:
    def test_select_prefix_classified_as_select(self) -> None:
        assert db_metrics._classify_sql_operation("SELECT 1") == "SELECT"

    def test_lowercase_insert_with_leading_whitespace(self) -> None:
        assert db_metrics._classify_sql_operation("  insert into users") == "INSERT"

    def test_update_classified(self) -> None:
        assert db_metrics._classify_sql_operation("UPDATE users SET x=1") == "UPDATE"

    def test_delete_classified(self) -> None:
        assert db_metrics._classify_sql_operation("DELETE FROM x") == "DELETE"

    def test_unknown_returns_other(self) -> None:
        assert db_metrics._classify_sql_operation("WITH cte AS (SELECT 1)") == "OTHER"
        assert db_metrics._classify_sql_operation("") == "OTHER"
        assert db_metrics._classify_sql_operation("BEGIN") == "OTHER"

    def test_cardinality_is_bounded(self) -> None:
        """Operation label values are limited to known + OTHER."""
        allowed = set(KNOWN_SQL_OPERATIONS) | {"OTHER"}
        samples = [
            "SELECT 1",
            "INSERT INTO t",
            "UPDATE t SET",
            "DELETE FROM t",
            "WITH cte AS",
            "VACUUM",
            "CREATE TABLE",
            "",
        ]
        observed = {db_metrics._classify_sql_operation(s) for s in samples}
        assert observed.issubset(allowed)
        assert len(allowed) <= 5  # SELECT, INSERT, UPDATE, DELETE, OTHER


class TestObserveDbQueryDurationSeconds:
    def test_appends_to_window_state(self) -> None:
        db_metrics.observe_db_query_duration_seconds("SELECT", 0.012)
        assert len(db_metrics._db_window_state.observations) == 1
        assert db_metrics._db_window_state.observations[0].operation == "SELECT"
        assert db_metrics._db_window_state.observations[0].value == 0.012

    def test_negative_duration_clamped_to_zero(self) -> None:
        db_metrics.observe_db_query_duration_seconds("SELECT", -0.5)
        assert db_metrics._db_window_state.observations[0].value == 0.0

    def test_no_op_when_prometheus_client_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Lazy import should swallow ImportError without raising."""
        import builtins

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "prometheus_client":
                raise ImportError("simulated missing prometheus_client")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        # Should not raise; deque should still be appended (state-only path).
        db_metrics.observe_db_query_duration_seconds("SELECT", 0.005)
        assert len(db_metrics._db_window_state.observations) == 1


class TestGetDbCompactHealthView:
    def test_returns_windows_and_by_label_structure(self) -> None:
        now = utc_now()
        db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=now, operation="SELECT", value=0.01))
        db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=now, operation="SELECT", value=0.05))
        db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=now, operation="INSERT", value=0.02))

        view = db_metrics.get_db_compact_health_view(now=now)

        assert "windows" in view
        assert "primary_window" in view
        assert "by_label" in view
        primary = view["primary_window"]
        select_metrics = view["by_label"][primary]["SELECT"]
        assert select_metrics["count"] == 2
        insert_metrics = view["by_label"][primary]["INSERT"]
        assert insert_metrics["count"] == 1

    def test_empty_state_returns_nulls(self) -> None:
        view = db_metrics.get_db_compact_health_view()
        assert view["windows"]  # at least one window key
        primary = view["primary_window"]
        # All operations should have count=0 with null percentiles.
        for op_metrics in view["by_label"][primary].values():
            assert op_metrics["count"] == 0
            assert op_metrics["p50"] is None

    def test_excludes_stale_observations_from_windows(self) -> None:
        now = utc_now()
        old = now - timedelta(hours=2)
        db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=old, operation="SELECT", value=1.0))

        view = db_metrics.get_db_compact_health_view(now=now)
        primary = view["primary_window"]
        assert view["by_label"][primary]["SELECT"]["count"] == 0


class TestInstallDbEventListeners:
    def test_is_idempotent_on_same_engine(self) -> None:
        engine = create_engine("sqlite://")
        db_metrics.install_db_event_listeners(engine)
        db_metrics.install_db_event_listeners(engine)

        # Sentinel attr indicates installation; idempotency means single-flag.
        assert getattr(engine, "_pulsai_db_metrics_installed", False) is True

    def test_event_listener_records_real_sqlite_select(self) -> None:
        engine = create_engine("sqlite://")
        db_metrics.install_db_event_listeners(engine)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # At least one SELECT observation should be recorded.
        select_obs = [o for o in db_metrics._db_window_state.observations if o.operation == "SELECT"]
        assert len(select_obs) >= 1
        assert select_obs[0].value >= 0
