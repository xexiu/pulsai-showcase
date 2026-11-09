"""SoT for the signal-freshness watcher (in-process lifespan tick).

This module centralises the env-driven config knobs for the freshness watcher
that catches silent signal-generation failures (e.g. data-source outage). The
watcher runs inside the API process — not a Celery worker — so it fires even
when all workers are dead.

All resolver functions accept an injectable ``env`` mapping so they are fully
unit-testable without patching ``os.environ``.

@see src/api/lifespan/signal_freshness_watch.py
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from src.shared.constants._env_resolvers import (
    env_source,
    resolve_positive_int,
)

# Private aliases so this module's own call sites are untouched by the consolidation.
_source = env_source
_resolve_positive_int = resolve_positive_int


# ---------------------------------------------------------------------------
# Env var names (SoT — never hard-coded in callers).
# ---------------------------------------------------------------------------
SIGNAL_FRESHNESS_WATCH_ENABLED_ENV_VAR: Final[str] = "SIGNAL_FRESHNESS_WATCH_ENABLED"
SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR: Final[str] = "SIGNAL_FRESHNESS_WATCH_INTERVAL_SECONDS"
SIGNAL_FRESHNESS_ALERT_COOLDOWN_ENV_VAR: Final[str] = "SIGNAL_FRESHNESS_ALERT_COOLDOWN_SECONDS"
SIGNAL_FRESHNESS_STALE_INTERVALS_ENV_VAR: Final[str] = "SIGNAL_FRESHNESS_STALE_INTERVALS"
SIGNAL_FRESHNESS_GRACE_ENV_VAR: Final[str] = "SIGNAL_FRESHNESS_GRACE_SECONDS"

# ---------------------------------------------------------------------------
# Defaults — low idle cost, generous cooldown to suppress spam.
# ---------------------------------------------------------------------------
DEFAULT_SIGNAL_FRESHNESS_WATCH_ENABLED: Final[bool] = True
DEFAULT_SIGNAL_FRESHNESS_WATCH_INTERVAL_SECONDS: Final[int] = 300  # 5-minute tick
DEFAULT_SIGNAL_FRESHNESS_ALERT_COOLDOWN_SECONDS: Final[int] = 1800  # 30-minute page cooldown
DEFAULT_SIGNAL_FRESHNESS_STALE_INTERVALS: Final[int] = 2  # stale after 2x timeframe

# Write-latency grace ON TOP of ``stale_intervals x timeframe``. NOT a fudge factor — without it
# the threshold is unreachable-by-construction in the healthy case, and pages on normal operation.
#
# A signal's ``created_at`` is the candle OPEN time. A bar opening at B closes at B+tf, and its
# signal is written at B+tf+e where e is beat-scheduling plus generation time. So in the window
# [B+2tf, B+2tf+e) the freshest signal that exists is already `2tf + e` old — and the bare
# `2 x tf` threshold called that STALE, every cycle, on every timeframe, forever.
#
# MEASURED in prod 2026-08-31 (the page that produced this constant): a BTC/USDT 1h alert reading
# "stale 7200s" — exactly the threshold, which is the tell — with generation at 10:00:04.2 and the
# watcher polling at 10:00:00.6, 3.6s earlier. Nothing had failed.
#
# SIZED at one live-signal beat period (``generate-live-signals-5min``, crontab minute="*/5"), the
# real upper bound on how late a closed bar's signal can be when the pipeline is working: a bar
# closing just after a tick waits for the next one. Observed generation latency was 1.7-4.2s, so
# this is ~70x the measured need — deliberately, because the defect being fixed IS a threshold
# with no headroom, and replacing it with a second tight threshold repeats the mistake.
#
# COST of the grace, stated plainly: a genuine outage is detected 5 minutes later than before
# (1h pair: 2h00 -> 2h05). Raising ``stale_intervals`` to 3 instead would have cost a full HOUR
# on the same pair, which is why the grace is the cheaper correction.
DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS: Final[int] = 300

# ---------------------------------------------------------------------------
# Redis throttle key — atomic SET NX EX cooldown. One canonical key.
# ---------------------------------------------------------------------------
SIGNAL_FRESHNESS_THROTTLE_KEY: Final[str] = "signal_freshness:cooldown"

# Cap stale pairs rendered into a single Telegram message so broad
# degradation can't produce a multi-KB push.
SIGNAL_FRESHNESS_MAX_ENTRIES: Final[int] = 10

_TRUE_TOKENS: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSE_TOKENS: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


def resolve_signal_freshness_watch_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Resolve the watcher on/off flag; unknown/missing → default.

    :param env: Environment mapping; defaults to ``os.environ`` (injectable).
    """
    raw = _source(env).get(SIGNAL_FRESHNESS_WATCH_ENABLED_ENV_VAR)
    if raw is None:
        return DEFAULT_SIGNAL_FRESHNESS_WATCH_ENABLED
    token = raw.strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return DEFAULT_SIGNAL_FRESHNESS_WATCH_ENABLED


def resolve_signal_freshness_watch_interval_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the watcher tick interval (seconds); missing/invalid → default."""
    return _resolve_positive_int(
        env=env,
        var=SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR,
        default=DEFAULT_SIGNAL_FRESHNESS_WATCH_INTERVAL_SECONDS,
    )


def resolve_signal_freshness_alert_cooldown_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the Telegram alert cooldown (seconds); missing/invalid → default."""
    return _resolve_positive_int(
        env=env,
        var=SIGNAL_FRESHNESS_ALERT_COOLDOWN_ENV_VAR,
        default=DEFAULT_SIGNAL_FRESHNESS_ALERT_COOLDOWN_SECONDS,
    )


def resolve_signal_freshness_stale_intervals(env: Mapping[str, str] | None = None) -> int:
    """Resolve the stale-interval multiplier; missing/invalid → default.

    A pair is stale when ``now - latest_signal > stale_intervals x timeframe_delta + grace``.
    """
    return _resolve_positive_int(
        env=env,
        var=SIGNAL_FRESHNESS_STALE_INTERVALS_ENV_VAR,
        default=DEFAULT_SIGNAL_FRESHNESS_STALE_INTERVALS,
    )


def resolve_signal_freshness_grace_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the write-latency grace (seconds); missing/invalid → default.

    Added to the stale threshold so the pipeline's own candle-close write latency cannot page.
    See :data:`DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS` for why the bare multiple was unreachable.
    """
    return _resolve_positive_int(
        env=env,
        var=SIGNAL_FRESHNESS_GRACE_ENV_VAR,
        default=DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS,
    )


__all__ = [
    "DEFAULT_SIGNAL_FRESHNESS_ALERT_COOLDOWN_SECONDS",
    "DEFAULT_SIGNAL_FRESHNESS_GRACE_SECONDS",
    "DEFAULT_SIGNAL_FRESHNESS_STALE_INTERVALS",
    "DEFAULT_SIGNAL_FRESHNESS_WATCH_ENABLED",
    "DEFAULT_SIGNAL_FRESHNESS_WATCH_INTERVAL_SECONDS",
    "SIGNAL_FRESHNESS_ALERT_COOLDOWN_ENV_VAR",
    "SIGNAL_FRESHNESS_GRACE_ENV_VAR",
    "SIGNAL_FRESHNESS_MAX_ENTRIES",
    "SIGNAL_FRESHNESS_STALE_INTERVALS_ENV_VAR",
    "SIGNAL_FRESHNESS_THROTTLE_KEY",
    "SIGNAL_FRESHNESS_WATCH_ENABLED_ENV_VAR",
    "SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR",
    "resolve_signal_freshness_alert_cooldown_seconds",
    "resolve_signal_freshness_grace_seconds",
    "resolve_signal_freshness_stale_intervals",
    "resolve_signal_freshness_watch_enabled",
    "resolve_signal_freshness_watch_interval_seconds",
]
