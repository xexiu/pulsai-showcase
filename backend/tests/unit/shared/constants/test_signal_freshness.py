"""Unit tests for the signal-freshness SoT constants + resolvers.

All resolvers accept an injectable ``env`` mapping so tests never patch
``os.environ``.
"""

from __future__ import annotations

import pytest

from src.shared.constants.signal_freshness import (
    DEFAULT_SIGNAL_FRESHNESS_ALERT_COOLDOWN_SECONDS,
    DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS,
    DEFAULT_SIGNAL_FRESHNESS_STALE_INTERVALS,
    DEFAULT_SIGNAL_FRESHNESS_WATCH_ENABLED,
    DEFAULT_SIGNAL_FRESHNESS_WATCH_INTERVAL_SECONDS,
    SIGNAL_FRESHNESS_ALERT_COOLDOWN_ENV_VAR,
    SIGNAL_FRESHNESS_GRACE_ENV_VAR,
    SIGNAL_FRESHNESS_MAX_ENTRIES,
    SIGNAL_FRESHNESS_STALE_INTERVALS_ENV_VAR,
    SIGNAL_FRESHNESS_THROTTLE_KEY,
    SIGNAL_FRESHNESS_WATCH_ENABLED_ENV_VAR,
    SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR,
    resolve_signal_freshness_alert_cooldown_seconds,
    resolve_signal_freshness_grace_seconds,
    resolve_signal_freshness_stale_intervals,
    resolve_signal_freshness_watch_enabled,
    resolve_signal_freshness_watch_interval_seconds,
)

# ---------------------------------------------------------------------------
# Constants shape
# ---------------------------------------------------------------------------


def test_throttle_key_format() -> None:
    assert SIGNAL_FRESHNESS_THROTTLE_KEY == "signal_freshness:cooldown"


def test_max_entries_positive() -> None:
    assert SIGNAL_FRESHNESS_MAX_ENTRIES > 0


# ---------------------------------------------------------------------------
# resolve_signal_freshness_watch_enabled
# ---------------------------------------------------------------------------


class TestResolveEnabled:
    def test_default_when_missing(self) -> None:
        assert resolve_signal_freshness_watch_enabled({}) is DEFAULT_SIGNAL_FRESHNESS_WATCH_ENABLED

    @pytest.mark.parametrize("token", ["1", "true", "TRUE", "yes", "On"])
    def test_truthy_tokens(self, token: str) -> None:
        assert resolve_signal_freshness_watch_enabled({SIGNAL_FRESHNESS_WATCH_ENABLED_ENV_VAR: token}) is True

    @pytest.mark.parametrize("token", ["0", "false", "no", "OFF"])
    def test_falsy_tokens(self, token: str) -> None:
        assert resolve_signal_freshness_watch_enabled({SIGNAL_FRESHNESS_WATCH_ENABLED_ENV_VAR: token}) is False

    def test_garbage_falls_back_to_default(self) -> None:
        assert resolve_signal_freshness_watch_enabled({SIGNAL_FRESHNESS_WATCH_ENABLED_ENV_VAR: "maybe"}) is DEFAULT_SIGNAL_FRESHNESS_WATCH_ENABLED


# ---------------------------------------------------------------------------
# resolve_signal_freshness_watch_interval_seconds
# ---------------------------------------------------------------------------


class TestResolveInterval:
    def test_default_when_missing(self) -> None:
        assert resolve_signal_freshness_watch_interval_seconds({}) == DEFAULT_SIGNAL_FRESHNESS_WATCH_INTERVAL_SECONDS

    def test_custom_value(self) -> None:
        assert resolve_signal_freshness_watch_interval_seconds({SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR: "120"}) == 120

    @pytest.mark.parametrize("bad", ["0", "-5", "abc", ""])
    def test_invalid_falls_back_to_default(self, bad: str) -> None:
        assert (
            resolve_signal_freshness_watch_interval_seconds({SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR: bad})
            == DEFAULT_SIGNAL_FRESHNESS_WATCH_INTERVAL_SECONDS
        )


# ---------------------------------------------------------------------------
# resolve_signal_freshness_alert_cooldown_seconds
# ---------------------------------------------------------------------------


class TestResolveCooldown:
    def test_default_when_missing(self) -> None:
        assert resolve_signal_freshness_alert_cooldown_seconds({}) == DEFAULT_SIGNAL_FRESHNESS_ALERT_COOLDOWN_SECONDS

    def test_custom_value(self) -> None:
        assert resolve_signal_freshness_alert_cooldown_seconds({SIGNAL_FRESHNESS_ALERT_COOLDOWN_ENV_VAR: "600"}) == 600

    @pytest.mark.parametrize("bad", ["0", "-1", "garbage", ""])
    def test_invalid_falls_back_to_default(self, bad: str) -> None:
        assert (
            resolve_signal_freshness_alert_cooldown_seconds({SIGNAL_FRESHNESS_ALERT_COOLDOWN_ENV_VAR: bad})
            == DEFAULT_SIGNAL_FRESHNESS_ALERT_COOLDOWN_SECONDS
        )


# ---------------------------------------------------------------------------
# resolve_signal_freshness_stale_intervals
# ---------------------------------------------------------------------------


class TestResolveGraceSeconds:
    """The write-latency grace resolves like every other knob — and must never be zero by default.

    A zero default would restore the exact prod defect this constant was created for: the bare
    ``2 x timeframe`` threshold is unreachable in the healthy case, because a signal is stamped
    with its candle's OPEN time and the freshest one that can exist is already ``2 x tf + write
    latency`` old. That paged the owner on 2026-08-31 with "stale 7200s" — the threshold value
    itself — while nothing had failed.
    """

    def test_default_when_missing(self) -> None:
        assert resolve_signal_freshness_grace_seconds({}) == DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS

    def test_custom_value(self) -> None:
        assert resolve_signal_freshness_grace_seconds({SIGNAL_FRESHNESS_GRACE_ENV_VAR: "45"}) == 45

    @pytest.mark.parametrize("bad", ["0", "-30", "soon", ""])
    def test_invalid_falls_back_to_default(self, bad: str) -> None:
        resolved = resolve_signal_freshness_grace_seconds({SIGNAL_FRESHNESS_GRACE_ENV_VAR: bad})
        assert resolved == DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS

    def test_the_default_clears_the_structural_floor(self) -> None:
        """The grace must exceed real generation latency, or it fixes nothing.

        Measured in prod 2026-08-31: the live-signal task took 1.66s and 4.15s on the two ticks
        either side of the false page. The default is one beat period, which is far above that —
        deliberate headroom, because the defect being corrected IS a threshold with none.
        """
        assert DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS > 5


class TestResolveStaleIntervals:
    def test_default_when_missing(self) -> None:
        assert resolve_signal_freshness_stale_intervals({}) == DEFAULT_SIGNAL_FRESHNESS_STALE_INTERVALS

    def test_custom_value(self) -> None:
        assert resolve_signal_freshness_stale_intervals({SIGNAL_FRESHNESS_STALE_INTERVALS_ENV_VAR: "3"}) == 3

    @pytest.mark.parametrize("bad", ["0", "-2", "nope", ""])
    def test_invalid_falls_back_to_default(self, bad: str) -> None:
        assert resolve_signal_freshness_stale_intervals({SIGNAL_FRESHNESS_STALE_INTERVALS_ENV_VAR: bad}) == DEFAULT_SIGNAL_FRESHNESS_STALE_INTERVALS
