"""Unit tests for the spike-alert SoT constants + resolvers (T1-5)."""

from __future__ import annotations

import pytest

from src.shared.constants.spike_alert import (
    COMPACT_STATUS_CRITICAL,
    COMPACT_STATUS_OK,
    COMPACT_STATUS_SEVERITY,
    COMPACT_STATUS_UNKNOWN,
    COMPACT_STATUS_WARN,
    DEFAULT_SPIKE_ALERT_COOLDOWN_SECONDS,
    DEFAULT_SPIKE_ALERT_MIN_SAMPLES,
    DEFAULT_SPIKE_ALERT_NOTIFY_MIN_SEVERITY,
    DEFAULT_SPIKE_ALERT_STARTUP_GRACE_SECONDS,
    DEFAULT_SPIKE_WATCH_ENABLED,
    DEFAULT_SPIKE_WATCH_INTERVAL_SECONDS,
    SPIKE_ALERT_COOLDOWN_ENV_VAR,
    SPIKE_ALERT_MIN_SAMPLES_ENV_VAR,
    SPIKE_ALERT_NOTIFY_MIN_SEVERITY_ENV_VAR,
    SPIKE_ALERT_STARTUP_GRACE_ENV_VAR,
    SPIKE_WATCH_ENABLED_ENV_VAR,
    SPIKE_WATCH_INTERVAL_ENV_VAR,
    resolve_spike_alert_cooldown_seconds,
    resolve_spike_alert_min_samples,
    resolve_spike_alert_notify_min_severity,
    resolve_spike_alert_startup_grace_seconds,
    resolve_spike_watch_enabled,
    resolve_spike_watch_interval_seconds,
)


def test_status_values_match_compact_view_helper_literals() -> None:
    # These MUST equal the literals the observability helper historically
    # emitted; the helper now imports them from here (single source).
    assert COMPACT_STATUS_OK == "ok"
    assert COMPACT_STATUS_WARN == "warn"
    assert COMPACT_STATUS_CRITICAL == "critical"
    assert COMPACT_STATUS_UNKNOWN == "unknown"


def test_severity_ordering_unknown_below_ok() -> None:
    sev = COMPACT_STATUS_SEVERITY
    assert sev[COMPACT_STATUS_UNKNOWN] < sev[COMPACT_STATUS_OK]
    assert sev[COMPACT_STATUS_OK] < sev[COMPACT_STATUS_WARN] < sev[COMPACT_STATUS_CRITICAL]


class TestResolveEnabled:
    def test_default_when_missing(self) -> None:
        assert resolve_spike_watch_enabled({}) is DEFAULT_SPIKE_WATCH_ENABLED

    @pytest.mark.parametrize("token", ["1", "true", "TRUE", "yes", "On"])
    def test_truthy_tokens(self, token: str) -> None:
        assert resolve_spike_watch_enabled({SPIKE_WATCH_ENABLED_ENV_VAR: token}) is True

    @pytest.mark.parametrize("token", ["0", "false", "no", "OFF"])
    def test_falsy_tokens(self, token: str) -> None:
        assert resolve_spike_watch_enabled({SPIKE_WATCH_ENABLED_ENV_VAR: token}) is False

    def test_garbage_falls_back_to_default(self) -> None:
        assert resolve_spike_watch_enabled({SPIKE_WATCH_ENABLED_ENV_VAR: "maybe"}) is DEFAULT_SPIKE_WATCH_ENABLED


class TestResolvePositiveInts:
    def test_interval_default(self) -> None:
        assert resolve_spike_watch_interval_seconds({}) == DEFAULT_SPIKE_WATCH_INTERVAL_SECONDS

    def test_interval_custom(self) -> None:
        assert resolve_spike_watch_interval_seconds({SPIKE_WATCH_INTERVAL_ENV_VAR: "30"}) == 30

    @pytest.mark.parametrize("bad", ["0", "-5", "abc", ""])
    def test_interval_invalid_falls_back(self, bad: str) -> None:
        assert resolve_spike_watch_interval_seconds({SPIKE_WATCH_INTERVAL_ENV_VAR: bad}) == DEFAULT_SPIKE_WATCH_INTERVAL_SECONDS

    def test_cooldown_custom_and_default(self) -> None:
        assert resolve_spike_alert_cooldown_seconds({}) == DEFAULT_SPIKE_ALERT_COOLDOWN_SECONDS
        assert resolve_spike_alert_cooldown_seconds({SPIKE_ALERT_COOLDOWN_ENV_VAR: "120"}) == 120

    def test_min_samples_custom_and_default(self) -> None:
        assert resolve_spike_alert_min_samples({}) == DEFAULT_SPIKE_ALERT_MIN_SAMPLES
        assert resolve_spike_alert_min_samples({SPIKE_ALERT_MIN_SAMPLES_ENV_VAR: "50"}) == 50


class TestResolveNotifyMinSeverity:
    def test_default_when_missing(self) -> None:
        assert resolve_spike_alert_notify_min_severity({}) == DEFAULT_SPIKE_ALERT_NOTIFY_MIN_SEVERITY

    @pytest.mark.parametrize("token", ["warn", "WARN", "critical"])
    def test_valid_paging_thresholds(self, token: str) -> None:
        assert resolve_spike_alert_notify_min_severity({SPIKE_ALERT_NOTIFY_MIN_SEVERITY_ENV_VAR: token}) == token.lower()

    @pytest.mark.parametrize("token", ["ok", "unknown", "panic", ""])
    def test_invalid_falls_back_to_critical(self, token: str) -> None:
        assert resolve_spike_alert_notify_min_severity({SPIKE_ALERT_NOTIFY_MIN_SEVERITY_ENV_VAR: token}) == DEFAULT_SPIKE_ALERT_NOTIFY_MIN_SEVERITY


class TestResolveStartupGrace:
    def test_default_when_missing(self) -> None:
        assert resolve_spike_alert_startup_grace_seconds({}) == DEFAULT_SPIKE_ALERT_STARTUP_GRACE_SECONDS

    def test_zero_disables_grace(self) -> None:
        assert resolve_spike_alert_startup_grace_seconds({SPIKE_ALERT_STARTUP_GRACE_ENV_VAR: "0"}) == 0

    def test_custom_valid(self) -> None:
        assert resolve_spike_alert_startup_grace_seconds({SPIKE_ALERT_STARTUP_GRACE_ENV_VAR: "120"}) == 120

    @pytest.mark.parametrize("bad", ["-1", "abc", ""])
    def test_invalid_falls_back(self, bad: str) -> None:
        assert resolve_spike_alert_startup_grace_seconds({SPIKE_ALERT_STARTUP_GRACE_ENV_VAR: bad}) == DEFAULT_SPIKE_ALERT_STARTUP_GRACE_SECONDS
