"""The [start, end) window a backtest request asks for -- its defaults, its order rule, its cap.

IMPORTERS/CALLERS: backtest_async_and_models (/run-async) and backtest_hub (optimize /
walk-forward). backtest_run, backtest_sizing_robustness and backtest_compare_routes still
hand-roll the same lines; moving them here is tracked as BACKTEST-WINDOW-SOT-1, because touching
those three files owes their existing debt (9 noqa, a blind except, an await-in-loop).
AFFECTED API: no signature or response moves. DATA SCHEMAS: none.

REUSE-AUDIT: considered backtest_hub._parse_and_validate_date_range -- the one earlier attempt at
this home, private to the hub and with required dates only; replaced by these two functions so the
other four routes can use it too. Considered backtest_utils -- a grab-bag of equity/compare
helpers, not a request-contract module, and adding here keeps that file's debt out of this change.
The date PARSING stays where it lives (src.utils.datetime_utils); this module owns the RULES.
Not backtest_run_window either: that one decides where /run may HONESTLY start (the in-sample
clamp) -- a different decision with a different reason to change.

MEASURED 2026-09-25 by the duplicate-lines ratchet: the same five lines, with the 30-day default
retyped, sat in five route modules, and they had already drifted -- /run-async skipped the range
cap and /compare skipped the order check.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

from fastapi import HTTPException, status

from src.infrastructure.config.settings import settings
from src.utils.datetime_utils import parse_backtest_range_end_utc, parse_backtest_range_start_utc

#: How far back a request that names no start_date reaches from its end.
DEFAULT_BACKTEST_LOOKBACK_DAYS: Final[int] = 30


def resolve_backtest_window(start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]:
    """Parse a request's window: no end means now, no start means the default lookback before end.

    Raises:
        HTTPException: 400 when the start is not before the end.
    """
    end_dt = datetime.now(tz=UTC)
    if end_date:
        end_dt = parse_backtest_range_end_utc(end_date)
    start_dt = end_dt - timedelta(days=DEFAULT_BACKTEST_LOOKBACK_DAYS)
    if start_date:
        start_dt = parse_backtest_range_start_utc(start_date)
    if start_dt >= end_dt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be before end_date")
    return start_dt, end_dt


def enforce_backtest_range_cap(start_dt: datetime, end_dt: datetime) -> None:
    """Refuse a window longer than ``settings.max_backtest_range_days`` (the synchronous routes' cap).

    Raises:
        HTTPException: 400 naming the cap and the requested span.
    """
    range_days = (end_dt - start_dt).days
    if range_days > settings.max_backtest_range_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date range must not exceed {settings.max_backtest_range_days} days (got {range_days}).",
        )
