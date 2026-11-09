"""Behavior tests for observability compact-view p95 threshold resolution.

Root cause these guard against (false spike-health CRITICAL page, 2026-06-18):
the Redis op-latency thresholds were calibrated for **co-located** Redis
(warn 10ms / critical 50ms). On Railway, Redis is a networked managed add-on
and the latency wrapper measures wall-clock around the ``await`` (network RTT
+ event-loop scheduling delay), so a normal p95 of ~74ms tripped ``critical``
and paged admins.

Contract:
- ``resolve_redis_op_p95_{warn,critical}_seconds`` read a strictly-positive
  float env var, falling back to the networked-aware default on
  missing/invalid/non-positive input (mirrors the resolver convention in
  ``spike_alert`` / ``ohlcv_sources`` / ``signal_freshness``).
- The defaults are networked-aware, so an observed-normal Redis p95 (74ms)
  no longer classifies as ``critical``.
- ``RedisCompactThresholds()`` picks up the env override at instantiation
  (``default_factory``), so dev (tight) and networked prod (loose) tune
  independently with no redeploy.
"""

from __future__ import annotations

import pytest

from src.infrastructure.observability import db_metrics, redis_metrics
from src.infrastructure.observability._compact_view_helpers import (
    compute_threshold_status,
)
from src.shared.constants import observability_metrics as om
from src.shared.constants.spike_alert import (
    COMPACT_STATUS_CRITICAL,
    COMPACT_STATUS_OK,
    COMPACT_STATUS_WARN,
)

# Observed-normal Redis p95 from the 2026-06-18 false CRITICAL page.
_OBSERVED_EXISTS_P95_SECONDS = 0.074
_OBSERVED_GET_P95_SECONDS = 0.049


class TestResolveRedisOpP95WarnSeconds:
    def test_default_when_missing(self) -> None:
        assert om.resolve_redis_op_p95_warn_seconds(env={}) == om.REDIS_OP_P95_WARN_SECONDS

    def test_valid_override_applies(self) -> None:
        assert om.resolve_redis_op_p95_warn_seconds(env={om.REDIS_OP_P95_WARN_ENV_VAR: "0.2"}) == 0.2

    def test_invalid_falls_back_to_default(self) -> None:
        assert om.resolve_redis_op_p95_warn_seconds(env={om.REDIS_OP_P95_WARN_ENV_VAR: "abc"}) == om.REDIS_OP_P95_WARN_SECONDS

    @pytest.mark.parametrize("bad", ["0", "-0.1", "0.0"])
    def test_non_positive_falls_back_to_default(self, bad: str) -> None:
        assert om.resolve_redis_op_p95_warn_seconds(env={om.REDIS_OP_P95_WARN_ENV_VAR: bad}) == om.REDIS_OP_P95_WARN_SECONDS


class TestResolveRedisOpP95CriticalSeconds:
    def test_default_when_missing(self) -> None:
        assert om.resolve_redis_op_p95_critical_seconds(env={}) == om.REDIS_OP_P95_CRITICAL_SECONDS

    def test_valid_override_applies(self) -> None:
        assert om.resolve_redis_op_p95_critical_seconds(env={om.REDIS_OP_P95_CRITICAL_ENV_VAR: "0.3"}) == 0.3

    def test_invalid_falls_back_to_default(self) -> None:
        assert om.resolve_redis_op_p95_critical_seconds(env={om.REDIS_OP_P95_CRITICAL_ENV_VAR: "nope"}) == om.REDIS_OP_P95_CRITICAL_SECONDS

    @pytest.mark.parametrize("bad", ["0", "-0.1", "0.0"])
    def test_non_positive_falls_back_to_default(self, bad: str) -> None:
        assert om.resolve_redis_op_p95_critical_seconds(env={om.REDIS_OP_P95_CRITICAL_ENV_VAR: bad}) == om.REDIS_OP_P95_CRITICAL_SECONDS


class TestNetworkedDefaultsCalibration:
    """The new defaults must not page on networked-normal Redis latency."""

    def test_warn_default_is_networked_aware(self) -> None:
        # Co-located default was 10ms; networked Redis needs more headroom.
        assert om.REDIS_OP_P95_WARN_SECONDS >= 0.05

    def test_critical_default_above_observed_normal(self) -> None:
        # 74ms is normal-busy on networked Railway Redis; critical must sit above it.
        assert om.REDIS_OP_P95_CRITICAL_SECONDS > _OBSERVED_EXISTS_P95_SECONDS

    def test_observed_exists_p95_classifies_warn_not_critical(self) -> None:
        th = redis_metrics.RedisCompactThresholds()
        status = compute_threshold_status(
            _OBSERVED_EXISTS_P95_SECONDS,
            warn=th.op_p95_warn_seconds,
            critical=th.op_p95_critical_seconds,
        )
        assert status == COMPACT_STATUS_WARN
        assert status != COMPACT_STATUS_CRITICAL

    def test_observed_get_p95_classifies_ok(self) -> None:
        th = redis_metrics.RedisCompactThresholds()
        status = compute_threshold_status(
            _OBSERVED_GET_P95_SECONDS,
            warn=th.op_p95_warn_seconds,
            critical=th.op_p95_critical_seconds,
        )
        assert status == COMPACT_STATUS_OK


class TestRedisCompactThresholdsEnvWiring:
    """The dataclass default_factory reads env at instantiation (tunable)."""

    def test_defaults_match_constants(self) -> None:
        th = redis_metrics.RedisCompactThresholds()
        assert th.op_p95_warn_seconds == om.REDIS_OP_P95_WARN_SECONDS
        assert th.op_p95_critical_seconds == om.REDIS_OP_P95_CRITICAL_SECONDS

    def test_env_override_applies_at_instantiation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(om.REDIS_OP_P95_CRITICAL_ENV_VAR, "0.3")
        monkeypatch.setenv(om.REDIS_OP_P95_WARN_ENV_VAR, "0.08")
        th = redis_metrics.RedisCompactThresholds()
        assert th.op_p95_critical_seconds == 0.3
        assert th.op_p95_warn_seconds == 0.08

    def test_env_override_can_restore_tight_dev_bands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Co-located dev can opt back into the tight 50ms critical band.
        monkeypatch.setenv(om.REDIS_OP_P95_CRITICAL_ENV_VAR, "0.05")
        th = redis_metrics.RedisCompactThresholds()
        status = compute_threshold_status(
            _OBSERVED_EXISTS_P95_SECONDS,
            warn=th.op_p95_warn_seconds,
            critical=th.op_p95_critical_seconds,
        )
        assert status == COMPACT_STATUS_CRITICAL


# Observed-normal networked Timescale SELECT p95 from the 2026-06-18 spike alert body.
_OBSERVED_SELECT_P95_SECONDS = 0.242


class TestResolveDbSelectP95WarnSeconds:
    def test_default_when_missing(self) -> None:
        assert om.resolve_db_select_p95_warn_seconds(env={}) == om.DB_SELECT_P95_WARN_SECONDS

    def test_valid_override_applies(self) -> None:
        assert om.resolve_db_select_p95_warn_seconds(env={om.DB_SELECT_P95_WARN_ENV_VAR: "0.4"}) == 0.4

    def test_invalid_falls_back_to_default(self) -> None:
        assert om.resolve_db_select_p95_warn_seconds(env={om.DB_SELECT_P95_WARN_ENV_VAR: "abc"}) == om.DB_SELECT_P95_WARN_SECONDS

    @pytest.mark.parametrize("bad", ["0", "-0.1", "0.0"])
    def test_non_positive_falls_back_to_default(self, bad: str) -> None:
        assert om.resolve_db_select_p95_warn_seconds(env={om.DB_SELECT_P95_WARN_ENV_VAR: bad}) == om.DB_SELECT_P95_WARN_SECONDS


class TestResolveDbSelectP95CriticalSeconds:
    def test_default_when_missing(self) -> None:
        assert om.resolve_db_select_p95_critical_seconds(env={}) == om.DB_SELECT_P95_CRITICAL_SECONDS

    def test_valid_override_applies(self) -> None:
        assert om.resolve_db_select_p95_critical_seconds(env={om.DB_SELECT_P95_CRITICAL_ENV_VAR: "0.9"}) == 0.9

    def test_invalid_falls_back_to_default(self) -> None:
        assert om.resolve_db_select_p95_critical_seconds(env={om.DB_SELECT_P95_CRITICAL_ENV_VAR: "nope"}) == om.DB_SELECT_P95_CRITICAL_SECONDS

    @pytest.mark.parametrize("bad", ["0", "-0.1", "0.0"])
    def test_non_positive_falls_back_to_default(self, bad: str) -> None:
        assert om.resolve_db_select_p95_critical_seconds(env={om.DB_SELECT_P95_CRITICAL_ENV_VAR: bad}) == om.DB_SELECT_P95_CRITICAL_SECONDS


class TestDbSelectNetworkedCalibration:
    """Observed-normal networked Timescale SELECT p95 must not warn (alert-body noise)."""

    def test_warn_default_is_networked_aware(self) -> None:
        assert om.DB_SELECT_P95_WARN_SECONDS > _OBSERVED_SELECT_P95_SECONDS

    def test_observed_select_p95_classifies_ok(self) -> None:
        warn, critical = db_metrics.DbCompactThresholds().for_operation("SELECT")
        status = compute_threshold_status(_OBSERVED_SELECT_P95_SECONDS, warn=warn, critical=critical)
        assert status == COMPACT_STATUS_OK

    def test_genuinely_slow_select_still_warns(self) -> None:
        warn, critical = db_metrics.DbCompactThresholds().for_operation("SELECT")
        status = compute_threshold_status(warn + 0.05, warn=warn, critical=critical)
        assert status == COMPACT_STATUS_WARN

    def test_very_slow_select_still_critical(self) -> None:
        warn, critical = db_metrics.DbCompactThresholds().for_operation("SELECT")
        status = compute_threshold_status(critical + 0.1, warn=warn, critical=critical)
        assert status == COMPACT_STATUS_CRITICAL


class TestDbCompactThresholdsEnvWiring:
    def test_select_defaults_match_constants(self) -> None:
        th = db_metrics.DbCompactThresholds()
        assert th.select_p95_warn_seconds == om.DB_SELECT_P95_WARN_SECONDS
        assert th.select_p95_critical_seconds == om.DB_SELECT_P95_CRITICAL_SECONDS

    def test_select_env_override_applies_at_instantiation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(om.DB_SELECT_P95_WARN_ENV_VAR, "0.35")
        monkeypatch.setenv(om.DB_SELECT_P95_CRITICAL_ENV_VAR, "0.8")
        th = db_metrics.DbCompactThresholds()
        assert th.select_p95_warn_seconds == 0.35
        assert th.select_p95_critical_seconds == 0.8

    def test_env_override_can_restore_tight_dev_bands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Co-located dev can tighten the SELECT warn band so the observed-normal
        # 242ms re-classifies as a warn.
        monkeypatch.setenv(om.DB_SELECT_P95_WARN_ENV_VAR, "0.1")
        warn, critical = db_metrics.DbCompactThresholds().for_operation("SELECT")
        status = compute_threshold_status(_OBSERVED_SELECT_P95_SECONDS, warn=warn, critical=critical)
        assert status == COMPACT_STATUS_WARN
