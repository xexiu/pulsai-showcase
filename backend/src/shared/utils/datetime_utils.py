"""
Datetime utilities for consistent UTC handling across PulsAI.

WHY THIS MODULE EXISTS:
Python's datetime.fromisoformat() and Polars pl.from_epoch() both produce
naive datetimes (no tzinfo). PostgreSQL's TIMESTAMP WITH TIME ZONE interprets
naive values in the session timezone, which varies by server region
(e.g. Europe/Madrid CET, Asia/Tokyo JST). This caused the Feb 24 2026 data
inconsistency bug where identical timestamps produced different query results.

RULE: All datetimes entering the system (API requests, DB inserts, comparisons
with wall-clock "now") MUST pass through ensure_utc() or parse_datetime_utc() as
appropriate. Use :func:`utc_now` for current UTC time so tests can patch one entry point.

@see tests/unit/infrastructure/test_hardening_sprint.py

SoT: This module lives under ``src.shared.utils``; ``src.utils.datetime_utils`` re-exports
for backward compatibility (DRY audit — single utils namespace).
"""

from __future__ import annotations

import re
import time as _time
from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING, Protocol, SupportsInt, runtime_checkable

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt
    import pandas as pd


@runtime_checkable
class _HasTimestamp(Protocol):
    """A scalar with a `.timestamp()` (datetime, pd.Timestamp, ...): isinstance checks the method exists, as hasattr did."""

    def timestamp(self) -> float: ...


# Calendar date only (no time): dashboard sends YYYY-MM-DD for backtest ranges.
_BACKTEST_CALENDAR_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def utc_now() -> datetime:
    """
    Current time in UTC (timezone-aware).

    Prefer this over ``datetime.now(UTC)`` at call sites so integration tests can
    ``monkeypatch`` ``src.shared.utils.datetime_utils.utc_now`` (or the bound
    name on the importing module) for deterministic time.
    """
    return datetime.now(UTC)


def now_ms() -> int:
    """
    Current UTC wall-clock as epoch milliseconds (int).

    Prefer this over inline ``int(time.time() * 1000)`` so call sites share one
    SoT and tests can ``monkeypatch`` ``src.shared.utils.datetime_utils.now_ms``
    (or the bound name on the importing module) for deterministic time. Same
    contract as :func:`utc_now` but as epoch-ms for wire-format / cache-key
    callers (stream supervisor, OHLCV fetchers, response cache "now").
    """
    return int(_time.time() * 1000)


def ensure_utc(dt: datetime) -> datetime:
    """
    Normalize a datetime to UTC. Naive datetimes are assumed to be UTC.

    WHY not raise on naive input?
    All current producers (Polars, CCXT, frontend ISO strings) intend UTC
    but omit the tzinfo. Raising would break every call site. Instead we
    attach UTC explicitly — the same semantic the rest of the stack expects.

    Args:
        dt: A datetime that may or may not have tzinfo.

    Returns:
        The same instant, expressed in UTC.

    Aware inputs are CONVERTED, not passed through. Until 2026-08-06 this returned an aware
    datetime unchanged, so a `+05:00` input came back as `+05:00` while the docstring claimed
    "tzinfo=UTC guaranteed". Harmless for comparison and arithmetic (same instant), silently
    wrong for anything reading wall-clock components — e.g. `edge_book_cache_ttl_seconds`
    derives a daily refresh boundary via `.replace(hour=..., minute=...)`, which lands five
    hours off on a +05:00 input.

    Converting is strictly safer than not: the instant is preserved, so no correct call site
    can break, and any that reads `.hour`/`.day` is fixed.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def ensure_utc_pandas_index(index: pd.Index | pd.Series) -> pd.DatetimeIndex:
    """
    Normalize a pandas index to a UTC-aware DatetimeIndex.

    Same naive→UTC contract as :func:`ensure_utc`. Required when aligning
    multiple OHLCV close series (XS/VT panel): Polars→pandas can yield
    tz-naive indexes while other paths are tz-aware, and
    ``pd.DataFrame({...})`` then raises TypeError.

    Args:
        index: Any index (or datetime Series) convertible to DatetimeIndex (naive or aware).

    Returns:
        UTC-aware DatetimeIndex (naive localized as UTC; aware converted).
    """
    import pandas as pd

    dt_index = pd.DatetimeIndex(index)
    if dt_index.tz is None:
        return dt_index.tz_localize(UTC)
    return dt_index.tz_convert(UTC)


def parse_datetime_utc(iso_string: str) -> datetime:
    """
    Parse an ISO 8601 string and guarantee UTC timezone.

    Combines datetime.fromisoformat() + ensure_utc() into a single call
    so callers never forget the normalization step.

    Args:
        iso_string: ISO format string, e.g. "2026-02-24T08:00:00"
                    or "2026-02-24T08:00:00+00:00"

    Returns:
        Timezone-aware datetime in UTC.
    """
    return ensure_utc(datetime.fromisoformat(iso_string))


def parse_backtest_range_start_utc(iso_string: str) -> datetime:
    """
    Parse backtest ``start_date`` for range filtering.

    - Calendar ``YYYY-MM-DD`` (dashboard default): start of that **UTC** day (00:00:00).
    - Full ISO datetimes: same as :func:`parse_datetime_utc` after stripping whitespace.

    WHY: Keeps ``start_date`` / ``end_date`` symmetric and explicit at call sites.
    """
    return parse_datetime_utc(iso_string.strip())


def parse_backtest_range_end_utc(iso_string: str) -> datetime:
    """
    Parse backtest ``end_date`` for inclusive range filtering.

    - Calendar ``YYYY-MM-DD``: **end** of that **UTC** day (23:59:59.999999) so the last
      candle on that calendar day is included (date-only is not midnight at the start
      of ``end_date``, which previously dropped almost all bars on the last day).
    - Full ISO datetimes: same as :func:`parse_datetime_utc` (scripts, parity tooling).
    """
    raw = iso_string.strip()
    if _BACKTEST_CALENDAR_DATE_ONLY.match(raw):
        day = date.fromisoformat(raw)
        return datetime.combine(day, time.max, tzinfo=UTC)
    return parse_datetime_utc(raw)


def normalize_timestamp_scalar_to_utc(ts: object) -> datetime | None:
    """
    Normalize a single timestamp value (from Polars, pandas, JSON, cache) to UTC datetime.

    Used wherever we read "timestamp" from a DataFrame or API response and need
    a datetime for comparison or storage. Avoids duplicating int/float/datetime
    and to_pydatetime() handling in ohlcv_service, ohlcv_cache, etc.

    Args:
        ts: Scalar from df["timestamp"].max(), df["timestamp"][-1], or JSON.
            Supports: datetime, int (epoch ms), float (epoch ms), Polars/pandas scalar.

    Returns:
        UTC datetime, or None if ts is not a supported type.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ensure_utc(ts)
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000.0, tz=UTC)
    to_pydatetime = getattr(ts, "to_pydatetime", None)  # a pandas / polars scalar
    converted = to_pydatetime() if callable(to_pydatetime) else None
    return ensure_utc(converted) if isinstance(converted, datetime) else None


#: ``YYYY-MM-DD`` -- the width of an ISO calendar day at the head of any ISO timestamp string.
ISO_DAY_LEN = 10


def iso_day(value: object) -> str:
    """The ISO calendar day (``YYYY-MM-DD``) of a timestamp-like value.

    ONE rule for a bar's day and a tape row's day: the leading ``YYYY-MM-DD`` of the value's ISO
    string form, which is what a pandas ``Timestamp``, a ``datetime``, a ``date`` and an ISO string
    all start with. ``observation_day`` keys tape rows by it, so a tick that writes
    ``as_of=iso_day(panel.index[-1])`` can never disagree with the reader counting its days.
    """
    return str(value)[:ISO_DAY_LEN]


def utc_today() -> str:
    """Today's UTC calendar day as ``YYYY-MM-DD``, read through :func:`utc_now` so tests patch one clock."""
    return iso_day(utc_now())


def epoch_ms(values: pd.Series | pd.DatetimeIndex | pd.Index) -> npt.NDArray[np.int64]:
    """Epoch MILLISECONDS from pandas times of any resolution (naive read as UTC) -- the vector sibling of
    :func:`polars_timestamp_to_epoch_ms`.

    `ts` is a file-format contract; the resolution of a `dt` column is an implementation detail of pandas. Two writers
    conflated them with ``astype("int64") // 1_000_000`` and a ``# ns -> ms`` comment. `astype("int64")` returns the
    datetime's OWN unit, and pandas 2+ keeps `datetime64[ms]`/`[us]`/`[s]` instead of coercing to nanoseconds -- so on
    millisecond frames the divide writes a `ts` 1e6 too small. MEASURED 2026-09-06: 220 of 1,228 cached parquets carried
    a corrupt `ts`, every row wrong (a 2019 bar stored as `ts=1546300`, read back as 1970-01-01 00:25:46).

    Moved here from research/edge_hunt/feature_cache on 2026-10-12 (EPOCH-MS-HOME): named there, it was still re-derived
    inline at 8 sites no one searching pine/ or shared/ would find -- and the latest copy collapsed every bar LTF-GRID
    built into one. `as_unit("ms")` declares the TARGET unit, so the result is identical for s / ms / us / ns input.

    Values that are already datetimes (dtype kind "M": any unit, naive or aware) are READ, not parsed again:
    `pd.to_datetime(utc=True)` on a 10,080-bar UTC index cost 4.1 ms of a 4.3 ms call, the epoch read 0.04 ms
    (RECORD-1S, 2026-10-16). ensure_utc_pandas_index gives them the parse's UTC reading: a naive time localised as
    UTC, an aware one converted -- the same instants, so the same epoch ints.
    """
    import numpy as np
    import pandas as pd

    index = ensure_utc_pandas_index(values if values.dtype.kind == "M" else pd.to_datetime(values, utc=True))  # PANDAS-OK: ensure_utc_pandas_index
    return np.asarray(index.as_unit("ms").astype("int64").to_numpy(), dtype=np.int64)


def polars_timestamp_to_epoch_ms(value: object) -> int:
    """
    Convert Polars/API timestamp scalar to UTC epoch milliseconds (SoT).

    Single source of truth for "timestamp column value → JSON response ms".
    Used by market.py OHLCV and chart-indicators so all API responses use the
    same conversion. CRITICAL: Polars/CCXT produce naive datetimes meaning UTC;
    Python's datetime.timestamp() treats naive as LOCAL time. We normalize to
    UTC so server TZ (e.g. Europe/Madrid) does not shift candle times (-1h bug).

    Args:
        value: Scalar from df.iter_rows() or df["timestamp"][i]: int (ms), or
            datetime (naive UTC from pl.from_epoch, or timezone-aware).

    Returns:
        Epoch milliseconds (int). Returns 0 for None/invalid.

    @see src.api.v1.endpoints.market_chart_routes (get_market_ohlcv)
    """
    if value is None:
        return 0
    if isinstance(value, SupportsInt) and not isinstance(value, _HasTimestamp):
        return int(value)
    if isinstance(value, datetime):
        return int(ensure_utc(value).timestamp() * 1000)
    if isinstance(value, _HasTimestamp):
        return int(value.timestamp() * 1000)
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError(f"polars_timestamp_to_epoch_ms: no epoch ms for a {type(value).__name__}")
