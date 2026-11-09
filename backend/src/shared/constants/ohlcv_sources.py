"""SoT for Binance OHLCV source failover configuration.

This module centralises two things the OHLCV source resolver depends on:

* **Binance source inventory** — the ordered list of public Binance REST base URLs
  used for OHLCV candle fetching (``data-api.binance.vision`` first for lower
  global latency, then ``api.binance.com`` spot, then the operator-configured
  proxy last). Direct-first ordering ensures minimal added latency when all
  sources are reachable.
* **Failover config knobs** — env-driven, mirroring the resolver pattern in
  :mod:`src.shared.constants.spike_alert`. The resolver is OFF by default so
  existing signal-generation behavior is 100% unchanged until an operator
  explicitly enables it.

BINANCE-ONLY INVARIANT: every URL in the resolved list MUST be served by a
Binance host. The ML models are trained exclusively on Binance candle data; mixing
in Coinbase/Kraken/Bybit candles would silently corrupt signal quality. The guard
:func:`assert_binance_only_sources` is called at resolve time and raises
``ValueError`` if any URL violates this constraint.

Redis circuit-breaker key builders also live here (SoT for all key strings).

@see src/infrastructure/exchange/binance_ohlcv_source_resolver.py (consumer)
@see src/infrastructure/exchange/binance_rest_url_override.py (downstream)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from urllib.parse import urlparse

from src.shared.constants._env_resolvers import (
    env_source,
    resolve_non_negative_float,
    resolve_positive_float,
    resolve_positive_int,
)

# Private aliases so this module's own call sites are untouched by the consolidation.
_source = env_source
_resolve_positive_int = resolve_positive_int
_resolve_positive_float = resolve_positive_float
_resolve_non_negative_float = resolve_non_negative_float


# ---------------------------------------------------------------------------
# Known Binance host suffixes (allowlist).
# ---------------------------------------------------------------------------
# Every official Binance REST host that may serve OHLCV / time endpoints.
# Adding a new suffix is a deliberate architect decision — also update
# BINANCE_REST_HOSTS in binance_rest_url_override.py if the host serves REST.
ALLOWED_BINANCE_HOST_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        "data-api.binance.vision",
        "api.binance.com",
        "api1.binance.com",
        "api2.binance.com",
        "api3.binance.com",
        "api4.binance.com",
        "api-gcp.binance.com",
    }
)

# ---------------------------------------------------------------------------
# Ordered Binance base URLs used as failover candidates.
# ---------------------------------------------------------------------------
# api.binance.com is the canonical spot REST host: it serves the FULL ccxt
# surface, including the fapi/dapi endpoints ccxt's load_markets() pre-fetches.
# data-api.binance.vision is a PUBLIC-market-data host (klines/time/exchangeInfo
# only) with a different CDN/WAF posture — a useful warm-cache klines fallback,
# but it 404s the futures endpoints, so it CANNOT serve a cold ccxt load_markets.
BINANCE_SPOT_API: Final[str] = "https://api.binance.com"
DATA_API_BINANCE_VISION: Final[str] = "https://data-api.binance.vision"

# Path probed to determine liveness. GET → 200 + {"serverTime": <ms>}.
SOURCE_PROBE_PATH: Final[str] = "/api/v3/time"

# ---------------------------------------------------------------------------
# Watcher config — env var names + safe defaults (resolver pattern).
# ---------------------------------------------------------------------------
BINANCE_OHLCV_FAILOVER_ENABLED_ENV_VAR: Final[str] = "BINANCE_OHLCV_FAILOVER_ENABLED"
BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR: Final[str] = "BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS"
BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_ENV_VAR: Final[str] = "BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS"
BINANCE_OHLCV_PROBE_TIMEOUT_ENV_VAR: Final[str] = "BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS"
BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS_ENV_VAR: Final[str] = "BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS"
BINANCE_OHLCV_PROBE_CONFIRM_DELAY_ENV_VAR: Final[str] = "BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS"

# OFF by default: existing signal-generation behavior is unchanged until an
# operator opts in. The circuit breaker and alerting are no-ops when disabled.
DEFAULT_BINANCE_OHLCV_FAILOVER_ENABLED: Final[bool] = False
# How long (seconds) a tripped circuit breaker stays open before re-probing.
DEFAULT_BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS: Final[int] = 120
# How long a source stays shut when the failure is a POLICY, not a blip.
#
# HTTP 451 / 403 from Binance is a geo-block on the CALLER's IP — which is why both direct hosts
# fail together, and why re-probing every 120 s achieves nothing but noise. Six hours is chosen to
# be long enough that a blocked region is not re-probed on a signal-generation cadence, and short
# enough that a genuine policy change (or a move to unblocked egress) is picked up the same day
# without a redeploy.
DEFAULT_BINANCE_OHLCV_BLOCKED_COOLDOWN_SECONDS: Final[int] = 6 * 60 * 60
# Statuses that mean "this caller may not use this host", as opposed to "this host is having a
# moment". 451 is the explicit legal/geo block; 403 is how the same refusal often arrives.
BLOCKED_HTTP_STATUSES: Final[frozenset[int]] = frozenset({403, 451})
# Telegram alert throttle per-source per-state (prevent spam during prolonged outage).
DEFAULT_BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS: Final[int] = 900
# HTTP probe timeout — must be short so failover adds at most N x timeout latency.
DEFAULT_BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS: Final[float] = 3.0
# Require N consecutive failed probes before opening the breaker / TG-alerting.
# Default 2 absorbs single-shot Railway/Binance blips that otherwise flap ⚠️+✅.
DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS: Final[int] = 2
# Sleep between confirm attempts (seconds). Kept small so failover stays snappy.
DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS: Final[float] = 0.5

# ---------------------------------------------------------------------------
# Redis key builders (SoT — all key strings live here, nowhere else).
# ---------------------------------------------------------------------------
# Key for the "all sources unreachable" critical alert throttle.
ALL_DOWN_ALERT_KEY: Final[str] = "ohlcv:source:alert:all_down"

# ---------------------------------------------------------------------------
# Log event names (SoT — the resolver EMITS these, tooling MATCHES on them).
# ---------------------------------------------------------------------------
# ``scripts/count_ohlcv_failover_log_events.py`` greps production logs for these exact
# tokens. Producer and consumer previously held independent copies of the strings, so a
# rename in one place would silently zero the counts — and "down=0 recovered=0" reads as
# "no failovers happened", which is the most dangerous way for a measurement to be wrong.
LOG_EVENT_SOURCE_PROBE_FAILED: Final[str] = "ohlcv_source_probe_failed"
LOG_EVENT_SOURCE_RECOVERED: Final[str] = "ohlcv_source_recovered"
LOG_EVENT_ALL_SOURCES_UNREACHABLE: Final[str] = "ohlcv_all_sources_unreachable"
LOG_EVENT_SOURCE_SELECTED: Final[str] = "ohlcv_source_selected"

_TRUE_TOKENS: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSE_TOKENS: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


# ---------------------------------------------------------------------------
# Env resolvers (injectable env mapping for tests).
# ---------------------------------------------------------------------------


def resolve_binance_ohlcv_failover_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Resolve the failover on/off flag; unknown/missing → default (False).

    :param env: Environment mapping; defaults to ``os.environ`` (injectable).
    """
    raw = _source(env).get(BINANCE_OHLCV_FAILOVER_ENABLED_ENV_VAR)
    if raw is None:
        return DEFAULT_BINANCE_OHLCV_FAILOVER_ENABLED
    token = raw.strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return DEFAULT_BINANCE_OHLCV_FAILOVER_ENABLED


def resolve_binance_ohlcv_source_cooldown_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the circuit-breaker cooldown (seconds); missing/invalid → default."""
    return _resolve_positive_int(
        env=env,
        var=BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR,
        default=DEFAULT_BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS,
    )


def resolve_binance_ohlcv_source_alert_cooldown_seconds(env: Mapping[str, str] | None = None) -> int:
    """Resolve the Telegram alert throttle cooldown (seconds); missing/invalid → default."""
    return _resolve_positive_int(
        env=env,
        var=BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_ENV_VAR,
        default=DEFAULT_BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS,
    )


def resolve_binance_ohlcv_probe_timeout_seconds(env: Mapping[str, str] | None = None) -> float:
    """Resolve the HTTP probe timeout (seconds, float); missing/invalid → default."""
    return _resolve_positive_float(
        env=env,
        var=BINANCE_OHLCV_PROBE_TIMEOUT_ENV_VAR,
        default=DEFAULT_BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS,
    )


def resolve_binance_ohlcv_probe_confirm_attempts(env: Mapping[str, str] | None = None) -> int:
    """Resolve consecutive failed-probe count required before declaring a source down."""
    return _resolve_positive_int(
        env=env,
        var=BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS_ENV_VAR,
        default=DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS,
    )


def resolve_binance_ohlcv_probe_confirm_delay_seconds(env: Mapping[str, str] | None = None) -> float:
    """Resolve sleep between confirm probes (seconds); missing/invalid → default.

    Zero is valid (no sleep between confirm attempts) — useful in tests and when
    operators want the fastest possible failover after a confirmed failure.
    """
    return _resolve_non_negative_float(
        env=env,
        var=BINANCE_OHLCV_PROBE_CONFIRM_DELAY_ENV_VAR,
        default=DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS,
    )


# ---------------------------------------------------------------------------
# Binance-only invariant guard.
# ---------------------------------------------------------------------------


def _normalize_host(url: str) -> str:
    """Extract the hostname from *url* (scheme-insensitive, lower-cased)."""
    parsed = urlparse(url)
    # urlparse without scheme puts everything in path; hostname handles it cleanly.
    host = parsed.hostname or ""
    return host.lower()


def assert_binance_only_sources(urls: list[str], *, trusted_proxy: str) -> None:
    """Raise ``ValueError`` if any URL is neither a Binance host nor the trusted proxy.

    The ML signal model is trained exclusively on Binance OHLCV candles.
    Routing candle fetches through a non-Binance exchange (e.g. Coinbase,
    Kraken, Bybit) would silently corrupt model features with mismatched data.
    This guard enforces the invariant at configuration time.

    :param urls: List of base URLs to validate.
    :param trusted_proxy: The operator-configured proxy URL (always trusted regardless of host).
    :raises ValueError: If any URL is not a known Binance host and not the trusted proxy,
        naming the offending URL and the model-parity reason.
    """
    normalized_proxy_host = _normalize_host(trusted_proxy) if trusted_proxy else ""
    normalized_proxy_url = trusted_proxy.rstrip("/") if trusted_proxy else ""

    for url in urls:
        normalized_url = url.rstrip("/")
        host = _normalize_host(url)

        # Trusted proxy is always allowed (by URL equality).
        if normalized_proxy_url and normalized_url == normalized_proxy_url:
            continue

        # Also allow if the proxy host matches (covers http vs https variants of the same proxy).
        if normalized_proxy_host and host == normalized_proxy_host:
            continue

        # Check against known Binance host suffixes.
        is_binance = any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_BINANCE_HOST_SUFFIXES)
        if not is_binance:
            msg = (
                f"OHLCV source '{url}' (host: '{host}') is not a recognised Binance host "
                f"and is not the configured trusted proxy. "
                f"The ML signal model is trained exclusively on Binance candles — "
                f"routing candle fetches through a different exchange would silently "
                f"corrupt model features. Allowed suffixes: {sorted(ALLOWED_BINANCE_HOST_SUFFIXES)}"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Source list builder.
# ---------------------------------------------------------------------------


def resolve_binance_ohlcv_sources(proxy_base_url: str) -> list[str]:
    """Return the ordered, deduped list of Binance OHLCV base URLs for failover.

    Ordering rationale: ``api.binance.com`` FIRST — the canonical host serving
    the full ccxt surface, including the fapi/dapi endpoints ccxt's
    ``load_markets()`` pre-fetches (so it works on a cold connect).
    ``data-api.binance.vision`` SECOND — public-market-data host with a different
    CDN/WAF posture (survives some blocks api.binance.com doesn't), but it 404s
    the futures endpoints, so it can only serve a warm-cache klines fetch, never
    a cold ``load_markets``. Operator proxy LAST (non-Railway egress — only when
    both direct paths are geo-blocked).

    The proxy is appended only when it is non-empty AND not already in the list
    (e.g. if the operator sets the proxy to ``https://api.binance.com`` the
    list stays deduplicated and the direct host is used without an extra hop).

    :param proxy_base_url: Operator-configured proxy base URL (may be empty).
    :returns: Ordered list; always contains at least the two direct Binance hosts.
    """
    direct: list[str] = [BINANCE_SPOT_API, DATA_API_BINANCE_VISION]
    result: list[str] = list(direct)

    normalized_proxy = proxy_base_url.rstrip("/") if proxy_base_url else ""
    if normalized_proxy and normalized_proxy not in result:
        result.append(normalized_proxy)

    assert_binance_only_sources(result, trusted_proxy=normalized_proxy)
    return result


# ---------------------------------------------------------------------------
# Redis key builders (SoT).
# ---------------------------------------------------------------------------


def breaker_gate_key(source: str) -> str:
    """Return the Redis circuit-breaker gate key for a given source URL.

    :param source: The OHLCV source base URL.
    :returns: Redis key string, e.g. ``ohlcv:source:breaker:data-api.binance.vision``.
    """
    host = _normalize_host(source) or source.rstrip("/")
    return f"ohlcv:source:breaker:{host}"


def breaker_alert_key(source: str, state: str) -> str:
    """Return the Redis throttle key for a state-transition alert on a source.

    :param source: The OHLCV source base URL.
    :param state: Alert state label, e.g. ``"down"`` or ``"recovered"``.
    :returns: Redis key string, e.g. ``ohlcv:source:alert:down:data-api.binance.vision``.
    """
    host = _normalize_host(source) or source.rstrip("/")
    return f"ohlcv:source:alert:{state}:{host}"


__all__ = [
    "ALLOWED_BINANCE_HOST_SUFFIXES",
    "ALL_DOWN_ALERT_KEY",
    "BINANCE_OHLCV_FAILOVER_ENABLED_ENV_VAR",
    "BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS_ENV_VAR",
    "BINANCE_OHLCV_PROBE_CONFIRM_DELAY_ENV_VAR",
    "BINANCE_OHLCV_PROBE_TIMEOUT_ENV_VAR",
    "BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_ENV_VAR",
    "BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR",
    "BINANCE_SPOT_API",
    "BLOCKED_HTTP_STATUSES",
    "DATA_API_BINANCE_VISION",
    "DEFAULT_BINANCE_OHLCV_BLOCKED_COOLDOWN_SECONDS",
    "DEFAULT_BINANCE_OHLCV_FAILOVER_ENABLED",
    "DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS",
    "DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS",
    "DEFAULT_BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS",
    "DEFAULT_BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS",
    "DEFAULT_BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS",
    "LOG_EVENT_ALL_SOURCES_UNREACHABLE",
    "LOG_EVENT_SOURCE_PROBE_FAILED",
    "LOG_EVENT_SOURCE_RECOVERED",
    "LOG_EVENT_SOURCE_SELECTED",
    "SOURCE_PROBE_PATH",
    "assert_binance_only_sources",
    "breaker_alert_key",
    "breaker_gate_key",
    "resolve_binance_ohlcv_failover_enabled",
    "resolve_binance_ohlcv_probe_confirm_attempts",
    "resolve_binance_ohlcv_probe_confirm_delay_seconds",
    "resolve_binance_ohlcv_probe_timeout_seconds",
    "resolve_binance_ohlcv_source_alert_cooldown_seconds",
    "resolve_binance_ohlcv_source_cooldown_seconds",
    "resolve_binance_ohlcv_sources",
]
