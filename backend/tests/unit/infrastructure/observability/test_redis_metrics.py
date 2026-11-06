"""
RED tests for `pulsai_redis_op_duration_seconds` histogram + windowed compact view.

Behavior contract:
- `_classify_redis_command` returns the uppercased command for known names,
  `OTHER` for everything else. Cardinality bounded by `KNOWN_REDIS_COMMANDS`.
- `observe_redis_op_duration_seconds(command, duration_seconds)` records into
  a time-windowed deque AND the Prometheus histogram (no-op when
  `prometheus_client` unavailable).
- `get_redis_compact_health_view` returns `{windows, primary_window, by_label}`.
- `install_redis_command_wrapper(client)` wraps `execute_command`:
  - Records duration on success.
  - Records duration on exception, then re-raises.
  - Is idempotent (sentinel attr prevents double-wrap).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.observability import redis_metrics
from src.infrastructure.observability.redis_metrics import (
    _classify_redis_command,
    get_redis_compact_health_view,
    reset_unlabelled_redis_commands_for_tests,
    unlabelled_redis_commands,
)
from src.shared.constants.observability_metrics import KNOWN_REDIS_COMMANDS


@pytest.fixture(autouse=True)
def _reset_redis_metrics_state(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_metrics._redis_window_state = redis_metrics._RedisWindowState()
    monkeypatch.setattr(redis_metrics, "_warmup_grace_seconds", lambda: 0.0)


class TestClassifyRedisCommand:
    def test_known_uppercase(self) -> None:
        assert redis_metrics._classify_redis_command("GET") == "GET"

    def test_lowercase_known_normalized(self) -> None:
        assert redis_metrics._classify_redis_command("hget") == "HGET"

    def test_unknown_returns_other(self) -> None:
        assert redis_metrics._classify_redis_command("WEIRDCMD") == "OTHER"

    def test_empty_returns_other(self) -> None:
        assert redis_metrics._classify_redis_command("") == "OTHER"

    def test_cardinality_is_bounded(self) -> None:
        allowed = set(KNOWN_REDIS_COMMANDS) | {"OTHER"}
        samples = ["GET", "set", "DEL", "hgetall", "FOO", "bar", ""]
        observed = {redis_metrics._classify_redis_command(s) for s in samples}
        assert observed.issubset(allowed)


class TestObserveRedisOpDurationSeconds:
    def test_appends_to_window_state(self) -> None:
        redis_metrics.observe_redis_op_duration_seconds("GET", 0.001)
        assert len(redis_metrics._redis_window_state.observations) == 1
        assert redis_metrics._redis_window_state.observations[0].command == "GET"

    def test_negative_duration_clamped(self) -> None:
        redis_metrics.observe_redis_op_duration_seconds("GET", -0.1)
        assert redis_metrics._redis_window_state.observations[0].value == 0.0

    def test_no_op_when_prometheus_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "prometheus_client":
                raise ImportError
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        redis_metrics.observe_redis_op_duration_seconds("GET", 0.002)
        assert len(redis_metrics._redis_window_state.observations) == 1


class TestInstallRedisCommandWrapper:
    @pytest.mark.asyncio
    async def test_wrapper_records_on_success(self) -> None:
        client = _make_fake_client(return_value="OK")
        redis_metrics.install_redis_command_wrapper(client)

        result = await client.execute_command("GET", "key1")

        assert result == "OK"
        obs = redis_metrics._redis_window_state.observations
        assert len(obs) == 1
        assert obs[0].command == "GET"

    @pytest.mark.asyncio
    async def test_wrapper_records_on_exception_and_reraises(self) -> None:
        client = _make_fake_client(side_effect=RuntimeError("redis down"))
        redis_metrics.install_redis_command_wrapper(client)

        with pytest.raises(RuntimeError):
            await client.execute_command("SET", "key1", "v")

        obs = redis_metrics._redis_window_state.observations
        assert len(obs) == 1
        assert obs[0].command == "SET"

    @pytest.mark.asyncio
    async def test_wrapper_is_idempotent(self) -> None:
        client = _make_fake_client(return_value="OK")
        redis_metrics.install_redis_command_wrapper(client)
        first_wrapped = client.execute_command
        redis_metrics.install_redis_command_wrapper(client)
        # No re-wrapping; sentinel set after first install.
        assert client.execute_command is first_wrapped
        assert getattr(client, "_pulsai_metrics_installed", False) is True


class TestGetRedisCompactHealthView:
    def test_returns_windows_and_by_label(self) -> None:
        from src.shared.utils.datetime_utils import utc_now

        now = utc_now()
        redis_metrics._redis_window_state.observations.append(redis_metrics._TimedRedisValue(at=now, command="GET", value=0.001))
        view = redis_metrics.get_redis_compact_health_view(now=now)
        assert "windows" in view
        assert "primary_window" in view
        assert "by_label" in view
        primary = view["primary_window"]
        assert view["by_label"][primary]["GET"]["count"] == 1


def _make_fake_client(*, return_value: Any = None, side_effect: Exception | None = None) -> Any:
    """Build a stand-in object with an awaitable execute_command attribute."""

    class _FakeClient:
        pass

    client = _FakeClient()
    if side_effect is not None:
        client.execute_command = AsyncMock(side_effect=side_effect)
    else:
        client.execute_command = AsyncMock(return_value=return_value)
    return client


# REUSE-AUDIT: considered apps/api/tests/unit/infrastructure/observability/test_redis_metrics.py
# and this IS that file -- appended, reusing its imports rather than opening a second suite.
# Considered apps/api/src/infrastructure/observability/redis_metrics.py -- EXTENDED following the
# `_synthetic_redis_samples_dropped` precedent already in it (module counter + getter + reset +
# a field published in the view), not a new mechanism beside it.


class TestTheOtherBucketNamesWhatItSaw:
    """OTHER went CRITICAL in prod and could not say what it was.

    MEASURED on prod 2026-09-06 while the owner was reporting a page on every dashboard load:

        redis OTHER  n=25  p50 0.031s  p95 1.165s  p99 1.421s  CRITICAL

    A Redis command over a second matters twice: Redis is single-threaded, so one slow command
    delays every other client, and the resulting page names whichever dependency happened to be
    awaiting. This repo has already been fooled by that once -- 2026-08-07, paged at
    `GET p95=0.425s` while Redis itself measured 5.47 ms.

    And OTHER is unfalsifiable as shipped: 24 commands are labelled, everything else collapses
    into one bucket with no way to tell SETEX from a pipeline from a keyspace scan. Guessing was
    tried first and wasted the effort -- `scan_keys` looked like the culprit and its only caller
    turned out to be an admin IP listing, nowhere near a chart.

    Recording the NAMES is not a cardinality risk: they never become Prometheus labels, which is
    what the module docstring forbids. They are a bounded diagnostic field in the compact view,
    exactly like `synthetic_samples_dropped` -- a filter nobody can see is the defect this file
    already exists to prevent.
    """

    def setup_method(self) -> None:
        reset_unlabelled_redis_commands_for_tests()

    def test_an_unlabelled_command_is_remembered_by_name(self) -> None:
        _classify_redis_command("SETEX")

        assert "SETEX" in unlabelled_redis_commands()

    def test_a_labelled_command_is_not_recorded(self) -> None:
        """Only the bucket that cannot explain itself needs explaining."""
        for command in KNOWN_REDIS_COMMANDS:
            _classify_redis_command(command)

        assert unlabelled_redis_commands() == ()

    def test_the_same_command_is_recorded_once(self) -> None:
        for _ in range(5):
            _classify_redis_command("SETEX")

        assert unlabelled_redis_commands().count("SETEX") == 1

    def test_it_is_bounded_by_the_size_of_the_labelled_set(self) -> None:
        """A bound DERIVED rather than picked: never more unlabelled names than labelled ones.

        Unbounded, a caller issuing a distinct command per request would grow this without limit
        inside a metrics module -- the failure the capacity bound on the warm-target registry
        exists for, in a place with even less excuse for it.
        """
        for index in range(len(KNOWN_REDIS_COMMANDS) * 3):
            _classify_redis_command(f"UNKNOWN{index}")

        assert len(unlabelled_redis_commands()) <= len(KNOWN_REDIS_COMMANDS)

    def test_the_view_publishes_them(self) -> None:
        """Recorded and never published is the inert-value defect this repo has shipped twice."""
        _classify_redis_command("SETEX")

        view = get_redis_compact_health_view()

        assert "SETEX" in view["other_commands_seen"]

    def test_incrby_is_labelled_because_prod_named_it_too(self) -> None:
        """The SECOND command the field caught, and the one that was still paging.

        `client.incr(key)` sends INCRBY key 1, so a list holding INCR but not INCRBY missed every
        call the public rate limiter makes -- which is one per request. Measured after GETDEL was
        labelled: `redis OTHER critical p95 0.4588 n=21`, and `other_commands_seen` said INCRBY.
        """
        assert _classify_redis_command("INCRBY") == "INCRBY"
        assert unlabelled_redis_commands() == ()

    def test_getdel_is_labelled_because_prod_named_it(self) -> None:
        """The first thing the new field reported, and the reason it was worth building.

        `RedisDataOps.getdel` has always issued GETDEL; the labelled set never covered it, so its
        latency shared a bucket with every other unknown and could be neither attributed nor
        excluded. Prod named it within ten minutes of the field shipping.
        """
        assert _classify_redis_command("GETDEL") == "GETDEL"
        assert unlabelled_redis_commands() == ()

    def test_the_view_publishes_an_empty_list_when_nothing_was_unlabelled(self) -> None:
        """Absent and empty must not render the same: one is 'clean', the other is 'no data'."""
        view = get_redis_compact_health_view()

        assert view["other_commands_seen"] == []
