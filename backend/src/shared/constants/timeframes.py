"""
Timeframe constants.

Canonical timeframe definitions used throughout the application for:
- OHLCV data fetching (exchange API calls)
- Candle duration calculations
- Training data windowing
- Walk-forward validation splits
- Backend-supported timeframe filtering for public config

ARCHITECTURE:
- `TIMEFRAME_REGISTRY` is the single source of truth
- `TIMEFRAME_MS` and `TIMEFRAME_DELTA` are derived views for consumers
- settings.supported_timeframes acts only as a validated filter over this registry

ALIGNMENT (Phase 2 SoT):
- `domain/enums.Timeframe` enum member values MUST match TIMEFRAME_REGISTRY.keys() for
  supported timeframes. When adding a new registry key, add a corresponding Timeframe
  enum member. Tests in tests/shared/constants/test_timeframes.py enforce this.

TIME ALIGNMENT (SoT):
- `period_start_ms(now_ms, tf_ms)` = current period start (forming candle). Used by: ohlcv_fetcher,
  market endpoint, tests. Buckets are anchored to the exchange candle open (Monday for weekly,
  the epoch otherwise via `WEEKLY_CANDLE_OPEN_ANCHOR_MS`). Do not duplicate the floor elsewhere.
- `last_closed_start_ms(now_ms, tf_ms)` = last closed period start. Used by: ohlcv_fetcher,
  get_last_closed_dt. Derived from `period_start_ms`; do not duplicate the formula elsewhere.

@see docs/04-structural/CODING_STANDARDS.md - Section 2.0 DON'T REINVENT THE WHEEL
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

from src.shared.utils.datetime_utils import utc_now

# Phase 2 WS supervisor: ``OHLCVService`` treats heartbeat as fresh if
# ``now - received_at_ms <= multiplier * get_timeframe_ms(tf)``.
OHLCV_WS_HEARTBEAT_MAX_AGE_MULTIPLIER: Final[int] = 2


class CandleOpenAlignment(StrEnum):
    """How a timeframe's candle open aligns relative to the Unix epoch (exchange convention).

    Declared per timeframe in ``TIMEFRAME_REGISTRY`` so "where does a bucket start?" is
    data, not scattered ``if tf == ...`` branches (OCP). ``period_start_ms`` dispatches on it.

    - ``EPOCH``: bucket starts at ``floor(now / tf) * tf``. Correct for every timeframe whose
      period evenly divides a UTC day (1m…1d open at UTC midnight / top of hour) — these
      already coincide with the epoch.
    - ``WEEKLY_MONDAY``: bucket starts Monday 00:00 UTC. The epoch (1970-01-01) is a Thursday,
      so a fixed offset re-anchors the week (see ``WEEKLY_CANDLE_OPEN_ANCHOR_MS``).
    - ``THREE_DAY_BINANCE``: Binance native ``3d`` opens on the epoch + 1 calendar day grid.
      Naive epoch floor is always off by exactly one day vs live Binance klines. Bitget ``3d``
      uses a different phase — PulsAI chart/OHLCV SoT is Binance-canonical (same posture as
      weekly Monday).

    EXTENSION (calendar timeframes — 1M/3M/6M/1y): these are **not** fixed-duration, so the
    ms-floor model here cannot express them. Adding one requires (a) a new member, (b) a
    calendar-aware boundary strategy (datetime arithmetic, not ``tf_ms`` flooring), and (c)
    revisiting the ``timedelta``/``tf_ms`` assumptions across sync/cache. Until that exists,
    an unimplemented alignment fails fast (guard test + KeyError), never a silent chart gap.
    """

    EPOCH = "epoch"
    WEEKLY_MONDAY = "weekly_monday"
    THREE_DAY_BINANCE = "three_day_binance"


class TimeframeBand(StrEnum):
    """Which training band a timeframe belongs to — LOWER (LTF) or HIGHER (HTF).

    Owner spec (2026-08-12, GRID-SUBSET: dated quote): *"lower timeframes are 5m,15m,30m,1h,2h and Higher timeframes are
    4h,6h,8h,12h,1d ... SoT, centralized ... so later can train ML on HTF / on LTF shared SoT
    from BE"*.

    DECLARED PER TIMEFRAME, exactly like ``open_alignment`` above: adding a timeframe is then PURE
    DATA, where a pair of member tuples is a second copy of the registry that drifts from it (the
    ``CAPITAL_MODES`` and inert-``2h``/``6h`` precedents are recorded in ``timeframe_bands.py``).

    ``None`` means the timeframe is real and supported but is NOT a training-band member: ``3d``/``1w``
    are chart/analysis timeframes. None is deliberately not a default band — silently bucketing an
    unlisted timeframe is how a model gets trained on a grid nobody chose.

    ``1m`` joined LOWER on 2026-10-11 (owner: *"ALL must be for 1min timeframe ... add 1min to LTF"*):
    training, signal validation and the research sweeps take it. Serving stays opt-in --
    ``_DEFAULT_EXCLUDED_TIMEFRAMES`` keeps it off /config/public, the OHLCV sync and the cron.
    """

    LOWER = "ltf"
    HIGHER = "htf"


@dataclass(frozen=True)
class TimeframeDefinition:
    """Canonical metadata for a supported timeframe (immutable Value Object)."""

    value: str
    delta: timedelta
    open_alignment: CandleOpenAlignment = CandleOpenAlignment.EPOCH
    band: TimeframeBand | None = None

    @property
    def milliseconds(self) -> int:
        """Duration in milliseconds for exchange and chart consumers."""
        return int(self.delta.total_seconds() * 1000)


# ============================================================================
# CANONICAL REGISTRY
# ============================================================================

TIMEFRAME_REGISTRY: dict[str, TimeframeDefinition] = {
    # Ordered SHORTEST FIRST, and the order is part of the contract: the derived bands, grids,
    # reports and training sweeps all iterate this registry, and an unstable order makes every log
    # diff noise. `band` is the training-band SoT — see TimeframeBand.
    "1m": TimeframeDefinition(value="1m", delta=timedelta(minutes=1), band=TimeframeBand.LOWER),
    "5m": TimeframeDefinition(value="5m", delta=timedelta(minutes=5), band=TimeframeBand.LOWER),
    "15m": TimeframeDefinition(value="15m", delta=timedelta(minutes=15), band=TimeframeBand.LOWER),
    "30m": TimeframeDefinition(value="30m", delta=timedelta(minutes=30), band=TimeframeBand.LOWER),
    "1h": TimeframeDefinition(value="1h", delta=timedelta(hours=1), band=TimeframeBand.LOWER),
    # 2h and 6h complete the training bands (LTF ..2h, HTF 4h..1d). Both divide a UTC day evenly
    # (12 and 4 buckets), so EPOCH alignment is correct exactly as it is for 4h/8h/12h; neither
    # needs a new alignment strategy, which is what makes them a safe addition rather than the
    # calendar-timeframe case this module's `CandleOpenAlignment` docstring warns about.
    "2h": TimeframeDefinition(value="2h", delta=timedelta(hours=2), band=TimeframeBand.LOWER),
    "4h": TimeframeDefinition(value="4h", delta=timedelta(hours=4), band=TimeframeBand.HIGHER),
    "6h": TimeframeDefinition(value="6h", delta=timedelta(hours=6), band=TimeframeBand.HIGHER),
    "8h": TimeframeDefinition(value="8h", delta=timedelta(hours=8), band=TimeframeBand.HIGHER),
    "12h": TimeframeDefinition(value="12h", delta=timedelta(hours=12), band=TimeframeBand.HIGHER),
    "1d": TimeframeDefinition(value="1d", delta=timedelta(days=1), band=TimeframeBand.HIGHER),
    # 3d/1w carry no band on purpose: chart and analysis timeframes, not grids we train or certify
    # on. They stay in the registry, and in the default supported list, so charts keep working.
    "3d": TimeframeDefinition(
        value="3d",
        delta=timedelta(days=3),
        open_alignment=CandleOpenAlignment.THREE_DAY_BINANCE,
    ),
    "1w": TimeframeDefinition(
        value="1w",
        delta=timedelta(weeks=1),
        open_alignment=CandleOpenAlignment.WEEKLY_MONDAY,
    ),
}

SUPPORTED_TIMEFRAME_VALUES: list[str] = list(TIMEFRAME_REGISTRY.keys())

#: Timeframes kept OUT of the default deployment surface, trainable or not. `1m` is entitlement-gated
#: (`resolve_trading_timeframe_allowlist`) and syncs 1,440 rows/symbol/day into a prod DB volume that
#: has filled up once, so it ships only when an operator opts in via SUPPORTED_TIMEFRAMES. Named, not
#: a hand-typed complement, so the reason travels with the exclusion.
_DEFAULT_EXCLUDED_TIMEFRAMES: Final[frozenset[str]] = frozenset({"1m"})

#: What a deployment serves when SUPPORTED_TIMEFRAMES is unset — which is the live configuration:
#: none of the 72 production env vars sets it (verified 2026-08-12), so this list IS what prod
#: exposes on /config/public and what `get_default_sync_timeframes` feeds to the OHLCV sync task.
#: Derived from the registry so a new timeframe is served, synced and charted by declaring it once.
DEFAULT_SUPPORTED_TIMEFRAME_VALUES: list[str] = [tf for tf in TIMEFRAME_REGISTRY if tf not in _DEFAULT_EXCLUDED_TIMEFRAMES]
DEFAULT_TIMEFRAME = "1h"
DEFAULT_TIMEFRAME_DELTA = TIMEFRAME_REGISTRY[DEFAULT_TIMEFRAME].delta
DEFAULT_TIMEFRAME_MS = TIMEFRAME_REGISTRY[DEFAULT_TIMEFRAME].milliseconds

#: Every banded timeframe, shortest first. THE definition of "a timeframe we train and trade on",
#: derived from the `band` field so the two consumers below cannot disagree with the registry.
BANDED_TIMEFRAMES_ORDER: Final[tuple[str, ...]] = tuple(tf for tf, d in TIMEFRAME_REGISTRY.items() if d.band is not None)

# Timeframes valid for signal generation and model training = exactly the banded ones.
# WHY a subset of the registry: 1w/3d are product chart timeframes, not grids we train on.
# Single source of truth for generate_signal validation and train_model_cli.
VALID_TIMEFRAMES_SIGNAL_AND_TRAINING: frozenset[str] = frozenset(BANDED_TIMEFRAMES_ORDER)

# The banded timeframes PROD SERVES, shortest first (banded, not in `_DEFAULT_EXCLUDED_TIMEFRAMES`):
# the signal cron's "candle just closed" list, the Telegram/AI confluence lookups and the Telegram
# notify default. It equalled the trainable set until 1m (2026-10-11): a cron watching 1m closes
# would store signals for a timeframe prod syncs no OHLCV for. Derived, so a served band member fires.
ALIGNMENT_TIMEFRAMES_ORDER: tuple[str, ...] = tuple(tf for tf in BANDED_TIMEFRAMES_ORDER if tf not in _DEFAULT_EXCLUDED_TIMEFRAMES)

# Human-readable labels for public config / FE Select components (SoT).
TIMEFRAME_LABELS: Final[dict[str, str]] = {
    "1m": "1 Minute",
    "5m": "5 Minutes",
    "15m": "15 Minutes",
    "30m": "30 Minutes",
    "1h": "1 Hour",
    "2h": "2 Hours",
    "4h": "4 Hours",
    "6h": "6 Hours",
    "8h": "8 Hours",
    "12h": "12 Hours",
    "1d": "1 Day",
    "3d": "3 Days",
    "1w": "1 Week",
}

# BOTH directions, and the second one is the load-bearing half. The original check only caught a
# label for a timeframe that does not exist — harmless. The real defect is the reverse: a registry
# entry with NO label, because `build_public_timeframe_options` indexes TIMEFRAME_LABELS[tf]
# directly, so the first request to /config/public raises KeyError and the whole frontend fails to
# boot. That is precisely how 2h/6h shipped: registry-only, label-less, and silent until served.
_unknown_labels = set(TIMEFRAME_LABELS.keys()) - set(TIMEFRAME_REGISTRY.keys())
if _unknown_labels:
    raise ValueError(f"TIMEFRAME_LABELS has unknown registry keys: {sorted(_unknown_labels)}")

_unlabelled_timeframes = set(TIMEFRAME_REGISTRY.keys()) - set(TIMEFRAME_LABELS.keys())
if _unlabelled_timeframes:
    raise ValueError(
        f"TIMEFRAME_REGISTRY entries have no TIMEFRAME_LABELS entry: {sorted(_unlabelled_timeframes)}. "
        "build_public_timeframe_options indexes labels directly, so a missing label is a KeyError "
        "on GET /config/public."
    )


# ============================================================================
# DERIVED VIEWS
# ============================================================================

TIMEFRAME_DELTA: dict[str, timedelta] = {timeframe: definition.delta for timeframe, definition in TIMEFRAME_REGISTRY.items()}
TIMEFRAME_MS: dict[str, int] = {timeframe: definition.milliseconds for timeframe, definition in TIMEFRAME_REGISTRY.items()}

# Unknown / legacy timeframe strings sort after all registry keys (admin health, observability).
_UNKNOWN_TF_DURATION_SENTINEL_MS: Final[int] = max(TIMEFRAME_MS.values()) + 1


def timeframe_sort_key(timeframe: str) -> tuple[int, str]:
    """Sort key: duration ascending (``TIMEFRAME_MS``), then lexicographic tie-break."""
    return (TIMEFRAME_MS.get(timeframe, _UNKNOWN_TF_DURATION_SENTINEL_MS), timeframe)


def training_timeframes_ordered() -> tuple[str, ...]:
    """Ordered VALID_TIMEFRAMES_SIGNAL_AND_TRAINING for research scripts and CLIs."""
    return tuple(sorted(VALID_TIMEFRAMES_SIGNAL_AND_TRAINING, key=timeframe_sort_key))


def sort_timeframe_keys(keys: Iterable[str]) -> list[str]:
    """Return unique timeframe strings sorted by registry duration (SoT: ``TIMEFRAME_MS``)."""
    return sorted(set(keys), key=timeframe_sort_key)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


@dataclass(frozen=True)
class PublicTimeframeOption:
    """Registry-backed timeframe metadata for GET /config/public."""

    value: str
    ms: int
    label: str


def build_public_timeframe_options(supported_timeframes: Iterable[str]) -> list[PublicTimeframeOption]:
    """Build sorted public timeframe options from deployment-supported values."""
    options: list[PublicTimeframeOption] = []
    for tf in supported_timeframes:
        if tf not in TIMEFRAME_REGISTRY:
            continue
        definition = TIMEFRAME_REGISTRY[tf]
        options.append(
            PublicTimeframeOption(
                value=tf,
                ms=definition.milliseconds,
                label=TIMEFRAME_LABELS[tf],
            )
        )
    return sorted(options, key=lambda o: timeframe_sort_key(o.value))


def get_timeframe_ms(timeframe: str) -> int:
    """
    Get timeframe duration in milliseconds.

    Args:
        timeframe: Timeframe string (e.g., "1h", "4h")

    Returns:
        Duration in milliseconds

    Raises:
        ValueError: If timeframe is not supported

    Examples:
        >>> get_timeframe_ms("1h")
        3600000
    """
    if timeframe not in TIMEFRAME_REGISTRY:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}. Supported: {list(TIMEFRAME_REGISTRY.keys())}")
    return TIMEFRAME_REGISTRY[timeframe].milliseconds


def get_timeframe_delta(timeframe: str) -> timedelta:
    """
    Get timeframe duration as timedelta.

    Args:
        timeframe: Timeframe string (e.g., "1h", "4h")

    Returns:
        Duration as timedelta

    Raises:
        ValueError: If timeframe is not supported (callers can catch this explicitly)

    Examples:
        >>> get_timeframe_delta("1h")
        datetime.timedelta(seconds=3600)
    """
    if timeframe not in TIMEFRAME_REGISTRY:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}. Supported: {list(TIMEFRAME_REGISTRY.keys())}")
    return TIMEFRAME_REGISTRY[timeframe].delta


def is_intraday_timeframe(timeframe: str) -> bool:
    """True when candle duration is strictly shorter than one UTC day.

    SoT for research/edge_lab split heuristics (and domain ``Timeframe.is_intraday`` parity).
    ``3d`` / ``1w`` / ``1d`` are multi-day; ``12h`` and below are intraday.
    """
    return get_timeframe_delta(timeframe.strip().lower()) < timedelta(days=1)


def bars_per_day(timeframe: str) -> float:
    """How many candles of this timeframe close in one UTC day.

    MEASURED 2026-08-15: this was implemented THREE times, from three different authorities, and
    two of the three claimed in their own docstring to be the single source of truth:

        src/scripts/train_model_validation.py   TIMEFRAME_REGISTRY[tf].delta
            "Bars a timeframe produces per day (SoT: TIMEFRAME_REGISTRY, never a hardcoded map)."
        edge_hunt/hunt_loop_runner.py           BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME[tf] / 365
            "from the periods-per-year SoT (reuse, no hardcoded per-TF counts)"
        research/xs_trend_portfolio_ls.py       86_400 / ccxt.binance().parse_timeframe(tf)

    They agree on every intraday timeframe and DISAGREE on the two multi-day ones, because the
    periods-per-year table stores rounded INTEGERS and dividing them back by 365 does not recover
    the ratio:

        3d   0.333333 (registry)   vs  0.334247 (122/365)   +0.27%
        1w   0.142857 (registry)   vs  0.142466 (52/365)    -0.27%

    Small, and that is the point: a 0.3% disagreement between two functions both documented as
    THE source of truth is invisible until someone compares a 3d window computed by one path
    against the same window computed by the other, and then it reads as a data problem.

    Derived from the registry's own delta rather than any table, for the same reason
    `edge_grid_common.TF_SCALE` and `tf_grid.timeframe_ms` are derived: a map keyed by timeframe
    is a mirror of the timeframe list, and mirrors drift. Raises on an unknown timeframe --
    a silent per-timeframe default is what makes the drift invisible.
    """
    seconds = get_timeframe_delta(timeframe.strip().lower()).total_seconds()
    if seconds <= 0:
        raise ValueError(f"Timeframe {timeframe!r} has a non-positive duration")
    return timedelta(days=1).total_seconds() / seconds


def days_for_bars(timeframe: str, *, bars: int, floor_days: int = 0) -> int:
    """Calendar days a window needs so it can hold ``bars`` candles of this timeframe.

    ``floor_days`` is a RECENCY floor, never a cap: the result is the wider of the two, so a
    caller keeps its intraday window and only widens where the calendar makes the bar count
    impossible. Rounds UP -- a partial bar is not an observation.

    WHY THIS EXISTS, measured rather than asserted. Three places in this repo compute a day-window
    from a required bar count, and each inlined the arithmetic:

        train_model_validation._windows_for_timeframe   ceil(MIN_TRAIN_SAMPLES / bars_per_day)
        ARENA_BACKTEST_MIN_WINDOW_DAYS                  a 30-day floor beside a 100-bar gate
        load_rolling_sharpe_sample_size                 a flat 7 days beside a 20-observation gate

    The third one never did the arithmetic at all, and that is the whole defect: 7 days of 1d bars
    is 7 observations against a gate that demands 20, so the retraining CRITICAL tier could never
    fire on a daily model. A day-window and a bar-gate are different units, and units that are
    only converted in SOME call sites disagree exactly where nobody is looking.

    Raises on an unknown timeframe, like `bars_per_day` and for the same reason: a silent
    per-timeframe default is what makes this class of drift invisible.
    """
    if bars <= 0:
        return max(floor_days, 0)
    return max(floor_days, math.ceil(bars / bars_per_day(timeframe)))


def get_supported_timeframes(configured_timeframes: str | None) -> list[str]:
    """
    Resolve configured timeframes as a validated subset of the canonical registry.

    Blank configuration means "all known backend-supported timeframes".
    Unknown values fail fast to prevent config drift between env vars and code.
    """
    if not configured_timeframes or not configured_timeframes.strip():
        return SUPPORTED_TIMEFRAME_VALUES.copy()

    requested = [timeframe.strip() for timeframe in configured_timeframes.split(",") if timeframe.strip()]
    unknown = [timeframe for timeframe in requested if timeframe not in TIMEFRAME_REGISTRY]
    if unknown:
        raise ValueError(f"Unsupported timeframes in config: {unknown}. Supported: {SUPPORTED_TIMEFRAME_VALUES}")

    deduped: list[str] = []
    seen: set[str] = set()
    for timeframe in requested:
        if timeframe in seen:
            continue
        seen.add(timeframe)
        deduped.append(timeframe)
    return deduped


def hours_to_candles(hours: float, timeframe: str, min_candles: int = 1) -> int:
    """
    Convert a duration in hours to approximate number of candles for a timeframe.

    Uses TIMEFRAME_REGISTRY so timeframe definitions stay in one place.
    Used by retraining (min_new_samples check, volatility window) and similar logic.

    Args:
        hours: Duration in hours (e.g. 24 for one day, 720 for 30 days).
        timeframe: Timeframe string (e.g. "1h", "4h", "1d").
        min_candles: Minimum returned value (default 1).

    Returns:
        Number of candles that cover the given hours, at least min_candles.

    Examples:
        >>> hours_to_candles(24, "1h")
        24
        >>> hours_to_candles(24, "4h", min_candles=10)
        10
    """
    if timeframe not in TIMEFRAME_REGISTRY:
        # Fallback for unknown timeframe (e.g. tests); treat as 1h
        hours_per_candle = 1.0
    else:
        delta = TIMEFRAME_REGISTRY[timeframe].delta
        hours_per_candle = delta.total_seconds() / 3600.0
    if hours_per_candle <= 0:
        return min_candles
    n = int(hours / hours_per_candle)
    return max(min_candles, n)


# Exchanges (Binance et al.) open weekly candles on Monday 00:00 UTC. The Unix epoch
# (1970-01-01) is a Thursday, so a naive ``(now // wk) * wk`` floor anchors weekly buckets
# to Thursday and mislabels the week. The first Monday on/after the epoch is 1970-01-05
# (epoch + 4 days); that offset re-anchors weekly buckets to Monday. Every sub-week
# timeframe divides 4 days evenly, so the anchor is a mathematical no-op for them — only
# the weekly bucket shifts. SoT for the Monday anchor; do not hardcode 4-day offsets elsewhere.
WEEKLY_CANDLE_OPEN_ANCHOR_MS: Final[int] = int(timedelta(days=4).total_seconds() * 1000)

# Binance native ``3d`` opens are always one calendar day after the pure epoch 3d floor
# (verified live vs ``/api/v3/klines?interval=3d``). Re-anchor by +1 day so ``period_start_ms``
# matches exchange opens. SoT; do not hardcode 1-day offsets elsewhere.
THREE_DAY_BINANCE_CANDLE_OPEN_ANCHOR_MS: Final[int] = int(timedelta(days=1).total_seconds() * 1000)

# Epoch-relative anchor (ms) per alignment. SoT for anchors — do not hardcode offsets
# elsewhere. A missing entry is intentional fail-fast: a timeframe declaring an alignment
# with no fixed-ms anchor (e.g. calendar months, which are not fixed-duration) MUST be
# implemented via a dedicated calendar-aware boundary, not silently floored. Guarded by
# tests/shared/constants/test_timeframes.py::TestCandleOpenAlignmentRegistry.
_ALIGNMENT_ANCHOR_MS: Final[dict[CandleOpenAlignment, int]] = {
    CandleOpenAlignment.EPOCH: 0,
    CandleOpenAlignment.WEEKLY_MONDAY: WEEKLY_CANDLE_OPEN_ANCHOR_MS,
    CandleOpenAlignment.THREE_DAY_BINANCE: THREE_DAY_BINANCE_CANDLE_OPEN_ANCHOR_MS,
}

# Duration (ms) → declared alignment, derived from the registry (single source of truth).
# Adding an aligned timeframe is then pure data: declare ``open_alignment`` in the registry.
_TF_MS_TO_ALIGNMENT: Final[dict[int, CandleOpenAlignment]] = {
    definition.milliseconds: definition.open_alignment for definition in TIMEFRAME_REGISTRY.values()
}


def resolve_candle_open_alignment(tf_ms: int) -> CandleOpenAlignment:
    """Alignment declared for ``tf_ms`` in the registry; ``EPOCH`` for ad-hoc durations.

    EPOCH is the safe default: any timeframe whose period divides a UTC day already opens
    on the epoch grid, so an unregistered duration floors correctly.
    """
    return _TF_MS_TO_ALIGNMENT.get(tf_ms, CandleOpenAlignment.EPOCH)


def _period_alignment_anchor_ms(tf_ms: int) -> int:
    """Epoch-relative anchor so a period bucket starts at the exchange candle open.

    Dispatches on the timeframe's declared :class:`CandleOpenAlignment` (registry-driven),
    keeping the floor in :func:`period_start_ms` agnostic of any specific timeframe.
    """
    return _ALIGNMENT_ANCHOR_MS[resolve_candle_open_alignment(tf_ms)]


def period_start_ms(now_ms: int, tf_ms: int) -> int:
    """
    Start of the current period (forming candle) in epoch milliseconds.

    SoT for "current period start" used by OHLCV fetcher, market endpoint, and tests.
    Floors to the bucket anchored at the exchange candle open (Monday for weekly, the
    epoch otherwise); do not duplicate the floor elsewhere.

    Args:
        now_ms: Current time in epoch milliseconds (UTC).
        tf_ms: Timeframe duration in milliseconds (from get_timeframe_ms or TIMEFRAME_MS).

    Returns:
        Start of the current period in ms.

    Examples:
        At 11:30 UTC (1h): period_start_ms(now_ms, 3600_000) -> 11:00 UTC in ms.
        On Mon 2026-06-01 (1w): -> Monday 2026-06-01 00:00 UTC in ms (not the Thursday floor).
    """
    anchor = _period_alignment_anchor_ms(tf_ms)
    return ((now_ms - anchor) // tf_ms) * tf_ms + anchor


def last_closed_start_ms(now_ms: int, tf_ms: int) -> int:
    """
    Start of the last closed candle in epoch milliseconds.

    SoT for "last closed period start" (exclude current building bar). Derived from
    ``period_start_ms`` minus one period so the Monday weekly anchor is honored too.

    Args:
        now_ms: Current time in epoch milliseconds (UTC).
        tf_ms: Timeframe duration in milliseconds (from get_timeframe_ms or TIMEFRAME_MS).

    Returns:
        Start of the last closed period in ms.

    Examples:
        At 18:30 UTC (1h): last_closed_start_ms(now_ms, 3600_000) -> 17:00 UTC in ms.
        On Mon 2026-06-01 (1w): -> Monday 2026-05-25 00:00 UTC in ms.
    """
    return period_start_ms(now_ms, tf_ms) - tf_ms


def get_last_closed_dt(timeframe: str) -> datetime:
    """
    Return the open time of the last closed candle (exclude current building bar).

    Uses last_closed_start_ms(now_ms, timeframe) so repository and service
    "last N" window matches exchange "last N closed".

    Args:
        timeframe: Timeframe string (e.g., "1h", "4h")

    Returns:
        UTC datetime of the start of the last closed candle

    Examples:
        If now is 18:30 UTC, for "1h" returns 17:00 UTC (17:00-18:00 bar is closed).
    """
    now_ms = int(utc_now().timestamp() * 1000)
    tf_ms = get_timeframe_ms(timeframe)
    last_closed_ms = last_closed_start_ms(now_ms, tf_ms)
    return datetime.fromtimestamp(last_closed_ms / 1000.0, tz=UTC)
