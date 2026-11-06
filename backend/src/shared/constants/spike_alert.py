"""SoT for the spike-readiness health watcher (Twitter spike readiness — T1-5).

This module centralises two things the watcher depends on:

* **Compact-health status vocabulary** — the ``ok`` / ``warn`` / ``critical``
  / ``unknown`` literals produced by
  :func:`src.infrastructure.observability._compact_view_helpers.compute_threshold_status`.
  Both the producer (that helper) and the consumer (the spike evaluator)
  import them from here so the strings can never drift apart, and a worst-of
  reduction has one canonical severity ordering.
* **Watcher config knobs** — env-driven, mirroring the resolver pattern in
  :mod:`src.shared.constants.api_runtime` (``resolve_web_concurrency``). The
  watcher is cheap always-on insurance: it reads in-process metrics on a
  timer, logs a WARNING on saturation (visible in ``pulsai.log`` + the admin
  health UI), and pushes a throttled Telegram alert to admins on critical.
  Defaults keep idle cost/noise low: paging only on ``critical``, with a
  cooldown so a sustained spike can't spam the admin chat.

@see .cursor/plans/twitter_spike_readiness.plan.md (T1-5)
@see src/infrastructure/observability/_compact_view_helpers.py
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from src.shared.constants._env_resolvers import (
    env_source,
    resolve_bool,
    resolve_non_negative_int,
    resolve_positive_int,
)

# Private aliases so this module's own call sites are untouched by the consolidation.
_source = env_source
_resolve_positive_int = resolve_positive_int
_resolve_non_negative_int = resolve_non_negative_int


# ---------------------------------------------------------------------------
# Compact-health status vocabulary (SoT — see module docstring).
# ---------------------------------------------------------------------------
COMPACT_STATUS_OK: Final[str] = "ok"
COMPACT_STATUS_WARN: Final[str] = "warn"
COMPACT_STATUS_CRITICAL: Final[str] = "critical"
COMPACT_STATUS_UNKNOWN: Final[str] = "unknown"

# Worst-of ordering: higher = more severe. ``unknown`` (no samples) ranks
# below ``ok`` so empty windows never escalate an alert.
COMPACT_STATUS_SEVERITY: Final[Mapping[str, int]] = {
    COMPACT_STATUS_UNKNOWN: 0,
    COMPACT_STATUS_OK: 1,
    COMPACT_STATUS_WARN: 2,
    COMPACT_STATUS_CRITICAL: 3,
}


def status_severity(status: str) -> int:
    """Rank a compact status for worst-of reductions; unknown values rank lowest.

    Lived as a byte-identical private `_severity` in BOTH `spike_health_evaluator` and
    `spike_watch`, and a third copy was about to be written for the event-loop view. The
    ordering IS the vocabulary, so it belongs beside the vocabulary.
    """
    return COMPACT_STATUS_SEVERITY.get(status, 0)


def worst_status(*statuses: str) -> str:
    """The most severe of several statuses -- e.g. one metric judged on two thresholds.

    The event-loop view needs this: p95 answers "is the loop chronically late?" and the worst
    sample answers "did the loop stop?". A single freeze is invisible to the first and obvious
    to the second, so the badge must be the worse of the two rather than either alone.
    """
    if not statuses:
        return COMPACT_STATUS_UNKNOWN
    return max(statuses, key=status_severity)


# ---------------------------------------------------------------------------
# Watcher config — env var names + safe defaults (resolver pattern).
# ---------------------------------------------------------------------------
SPIKE_WATCH_ENABLED_ENV_VAR: Final[str] = "SPIKE_WATCH_ENABLED"
SPIKE_WATCH_INTERVAL_ENV_VAR: Final[str] = "SPIKE_WATCH_INTERVAL_SECONDS"
SPIKE_ALERT_COOLDOWN_ENV_VAR: Final[str] = "SPIKE_ALERT_COOLDOWN_SECONDS"
SPIKE_ALERT_MIN_SAMPLES_ENV_VAR: Final[str] = "SPIKE_ALERT_MIN_SAMPLES"
SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS_ENV_VAR: Final[str] = "SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS"
SPIKE_ALERT_NOTIFY_MIN_SEVERITY_ENV_VAR: Final[str] = "SPIKE_ALERT_NOTIFY_MIN_SEVERITY"
SPIKE_ALERT_STARTUP_GRACE_ENV_VAR: Final[str] = "SPIKE_ALERT_STARTUP_GRACE_SECONDS"
SPIKE_ALERT_ACTIVE_TTL_ENV_VAR: Final[str] = "SPIKE_ALERT_ACTIVE_TTL_SECONDS"

# On by default: the tick is a cheap in-process read; Telegram only fires on
# ``critical`` and is throttled, and is a no-op when no admin chat IDs exist.
DEFAULT_SPIKE_WATCH_ENABLED: Final[bool] = True
DEFAULT_SPIKE_WATCH_INTERVAL_SECONDS: Final[int] = 60
DEFAULT_SPIKE_ALERT_COOLDOWN_SECONDS: Final[int] = 900  # 15 min between pages
DEFAULT_SPIKE_ALERT_MIN_SAMPLES: Final[int] = 20  # ignore thin/noisy windows

#: How many CONSECUTIVE critical ticks a source+label must show before it may page.
#:
#: DERIVED FROM THE CORPUS, not picked. Measured 2026-09-06 over `spike_health_events`, 14 days,
#: 86 delivered pages, asking of each "was the same source+label still critical two ticks later?":
#:
#:     redis GET        15 pages   7 sustained
#:     redis EXISTS     14         5
#:     event_loop LAG   11         0        <- every one a transient
#:     db SELECT         9         3
#:     endpoint OTHER    9         7
#:     redis OTHER       9         5
#:     db INSERT         7         4
#:     redis EXPIRE      6         3
#:     chart-indicators  4         4        <- every one real
#:     market/ohlcv      2         0
#:
#: 48 of 86 (56%) had ALREADY RESOLVED by the time a human could look. Requiring the condition to
#: survive one more tick suppresses those and keeps all 38 that persisted -- including every
#: chart-indicators page, which is the one the owner actually needed.
#:
#: ARCHITECTURE_PATTERNS section 5, the circuit-breaker row: "thresholds are guesses until
#: measured. Too tight trips on noise; too loose never trips." A p95 over a 5-minute in-process
#: window that pages on ONE bad tick is the too-tight end, and this repo paid for it 48 times in
#: a fortnight. The cost of the fix is one tick (~60 s) of delay on a real page, which is the
#: right trade for a page that means something.
#:
#: 2 rather than 3: the measurement above covers exactly one extra tick, so 2 is the largest
#: value this corpus actually justifies. A higher number would be a guess again.
DEFAULT_SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS: Final[int] = 2
DEFAULT_SPIKE_ALERT_NOTIFY_MIN_SEVERITY: Final[str] = COMPACT_STATUS_CRITICAL
# Skip Telegram pages for this long after API process start. Covers Railway
# deploy cold-start (empty in-process metrics + cold chart-indicators/Redis/DB)
# so the 5m compact window does not page CRITICAL on every master push.
# Set to 0 to disable (tests / co-located debug).
DEFAULT_SPIKE_ALERT_STARTUP_GRACE_SECONDS: Final[int] = 300

# How long an unacknowledged page stays eligible for an all-clear.
#
# A TTL is REQUIRED, not decoration: without one, a flag written before a key was ever cleared
# would sit in Redis forever and announce "RECOVERED" for an incident nobody remembers, which is
# a worse failure than the silence it replaces. A day is long enough to cover any outage a human
# is still thinking about and short enough that a stale flag expires quietly on its own.
DEFAULT_SPIKE_ALERT_ACTIVE_TTL_SECONDS: Final[int] = 86_400

# Redis throttle key (atomic SET NX EX cooldown). One canonical key.
SPIKE_ALERT_THROTTLE_KEY: Final[str] = "spike_alert:cooldown"

# Redis key marking "a page was DELIVERED and its recovery has not been announced yet".
#
# In Redis rather than process memory because a push to master IS a deploy here, and the gap
# between a page and its recovery is measured in hours - 4.5 h in the case that prompted the
# all-clear. A deploy inside that window would restart the process, forget the outstanding
# page, and swallow the all-clear, reproducing the exact silence the all-clear exists to end.
# It also makes the flag correct across replicas: whichever process observes the healthy tick
# clears it, not only the process that happened to page.
SPIKE_ALERT_ACTIVE_KEY: Final[str] = "spike_alert:outstanding"

# Cap offenders rendered into a single Telegram message so a broad
# degradation can't produce a multi-KB push.
SPIKE_ALERT_MAX_OFFENDERS: Final[int] = 5


def resolve_spike_watch_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Resolve the watcher on/off flag; unknown/missing → default.

    The true/false token sets used to live here as module constants. They moved to
    ``_env_resolvers.resolve_bool`` on 2026-09-06 when a second caller appeared
    (``api_runtime.ensure_worker_count_is_safe``) — a second copy of a bool parser is precisely
    the clone that module was written to remove, and the behaviour here is unchanged.

    :param env: Environment mapping; defaults to ``os.environ`` (injectable).
    """
    return resolve_bool(
        env=env,
        var=SPIKE_WATCH_ENABLED_ENV_VAR,
        default=DEFAULT_SPIKE_WATCH_ENABLED,
    )


def resolve_spike_watch_interval_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the watcher tick interval (seconds); missing/invalid → default."""
    return _resolve_positive_int(
        env=env,
        var=SPIKE_WATCH_INTERVAL_ENV_VAR,
        default=DEFAULT_SPIKE_WATCH_INTERVAL_SECONDS,
    )


def resolve_spike_alert_cooldown_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the Telegram alert cooldown (seconds); missing/invalid → default."""
    return _resolve_positive_int(
        env=env,
        var=SPIKE_ALERT_COOLDOWN_ENV_VAR,
        default=DEFAULT_SPIKE_ALERT_COOLDOWN_SECONDS,
    )


def resolve_spike_alert_min_samples(env: Mapping[str, str] | None = None) -> int:
    """Resolve the min per-window sample count before a status can alert."""
    return _resolve_positive_int(
        env=env,
        var=SPIKE_ALERT_MIN_SAMPLES_ENV_VAR,
        default=DEFAULT_SPIKE_ALERT_MIN_SAMPLES,
    )


def resolve_spike_alert_consecutive_critical_ticks(env: Mapping[str, str] | None = None) -> int:
    """Resolve how many consecutive critical ticks are required before paging.

    1 restores the old page-on-one-tick behaviour, which the 14-day corpus shows is 56% noise.
    """
    return _resolve_positive_int(
        env=env,
        var=SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS_ENV_VAR,
        default=DEFAULT_SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS,
    )


def resolve_spike_alert_notify_min_severity(env: Mapping[str, str] | None = None) -> str:
    """Resolve the minimum severity that triggers a Telegram page.

    Only ``warn`` or ``critical`` are valid paging thresholds; any other
    value (missing, ``ok``, ``unknown``, garbage) falls back to the default
    (``critical``) so a typo can never silence paging entirely or page on
    healthy traffic.
    """
    raw = _source(env).get(SPIKE_ALERT_NOTIFY_MIN_SEVERITY_ENV_VAR)
    if raw is None:
        return DEFAULT_SPIKE_ALERT_NOTIFY_MIN_SEVERITY
    token = raw.strip().lower()
    if token in {COMPACT_STATUS_WARN, COMPACT_STATUS_CRITICAL}:
        return token
    return DEFAULT_SPIKE_ALERT_NOTIFY_MIN_SEVERITY


def resolve_spike_alert_startup_grace_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve post-boot Telegram suppress window (seconds); 0 disables grace."""
    return _resolve_non_negative_int(
        env=env,
        var=SPIKE_ALERT_STARTUP_GRACE_ENV_VAR,
        default=DEFAULT_SPIKE_ALERT_STARTUP_GRACE_SECONDS,
    )


def resolve_spike_alert_active_ttl_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve how long an unacknowledged page stays eligible for an all-clear (seconds)."""
    return _resolve_positive_int(
        env=env,
        var=SPIKE_ALERT_ACTIVE_TTL_ENV_VAR,
        default=DEFAULT_SPIKE_ALERT_ACTIVE_TTL_SECONDS,
    )


__all__ = [
    "COMPACT_STATUS_CRITICAL",
    "COMPACT_STATUS_OK",
    "COMPACT_STATUS_SEVERITY",
    "COMPACT_STATUS_UNKNOWN",
    "COMPACT_STATUS_WARN",
    "DEFAULT_SPIKE_ALERT_ACTIVE_TTL_SECONDS",
    "DEFAULT_SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS",
    "DEFAULT_SPIKE_ALERT_COOLDOWN_SECONDS",
    "DEFAULT_SPIKE_ALERT_MIN_SAMPLES",
    "DEFAULT_SPIKE_ALERT_NOTIFY_MIN_SEVERITY",
    "DEFAULT_SPIKE_ALERT_STARTUP_GRACE_SECONDS",
    "DEFAULT_SPIKE_WATCH_ENABLED",
    "DEFAULT_SPIKE_WATCH_INTERVAL_SECONDS",
    "SPIKE_ALERT_ACTIVE_KEY",
    "SPIKE_ALERT_ACTIVE_TTL_ENV_VAR",
    "SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS_ENV_VAR",
    "SPIKE_ALERT_COOLDOWN_ENV_VAR",
    "SPIKE_ALERT_MAX_OFFENDERS",
    "SPIKE_ALERT_MIN_SAMPLES_ENV_VAR",
    "SPIKE_ALERT_NOTIFY_MIN_SEVERITY_ENV_VAR",
    "SPIKE_ALERT_STARTUP_GRACE_ENV_VAR",
    "SPIKE_ALERT_THROTTLE_KEY",
    "SPIKE_WATCH_ENABLED_ENV_VAR",
    "SPIKE_WATCH_INTERVAL_ENV_VAR",
    "resolve_spike_alert_active_ttl_seconds",
    "resolve_spike_alert_consecutive_critical_ticks",
    "resolve_spike_alert_cooldown_seconds",
    "resolve_spike_alert_min_samples",
    "resolve_spike_alert_notify_min_severity",
    "resolve_spike_alert_startup_grace_seconds",
    "resolve_spike_watch_enabled",
    "resolve_spike_watch_interval_seconds",
    "status_severity",
    "worst_status",
]
