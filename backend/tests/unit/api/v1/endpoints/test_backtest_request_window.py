"""The backtest request window: one home for its defaults, its order rule and its range cap.

IMPORTERS/CALLERS: pytest only. AFFECTED API: pins backtest_request_window.resolve_backtest_window and
enforce_backtest_range_cap, which /run-async and the backtest hub resolve their [start, end)
through (the other three routes follow in BACKTEST-WINDOW-SOT-1). DATA SCHEMAS: none.

The same five lines were hand-written in five route modules (measured 2026-09-25 by the
duplicate-lines ratchet), with the 30-day default retyped in four of them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from src.api.v1.endpoints.backtest_request_window import (
    DEFAULT_BACKTEST_LOOKBACK_DAYS,
    enforce_backtest_range_cap,
    resolve_backtest_window,
)
from src.infrastructure.config.settings import settings


def test_an_omitted_end_is_now_and_an_omitted_start_is_the_default_lookback_before_it() -> None:
    before = datetime.now(tz=UTC)
    start_dt, end_dt = resolve_backtest_window(None, None)
    after = datetime.now(tz=UTC)

    assert before <= end_dt <= after
    assert end_dt - start_dt == timedelta(days=DEFAULT_BACKTEST_LOOKBACK_DAYS)


def test_explicit_dates_are_parsed_as_utc() -> None:
    start_dt, end_dt = resolve_backtest_window("2026-01-01", "2026-02-01")

    assert start_dt == datetime(2026, 1, 1, tzinfo=UTC)
    assert start_dt < end_dt
    assert end_dt.tzinfo is not None


def test_an_omitted_start_counts_back_from_an_explicit_end() -> None:
    start_dt, end_dt = resolve_backtest_window(None, "2026-02-01")

    assert end_dt - start_dt == timedelta(days=DEFAULT_BACKTEST_LOOKBACK_DAYS)


@pytest.mark.parametrize(("start", "end"), [("2026-02-01", "2026-01-01"), ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")])
def test_a_start_not_before_the_end_is_a_400(start: str, end: str) -> None:
    with pytest.raises(HTTPException) as caught:
        resolve_backtest_window(start, end)

    assert caught.value.status_code == 400
    assert caught.value.detail == "start_date must be before end_date"


def test_a_span_over_the_cap_is_a_400_naming_both_numbers() -> None:
    end_dt = datetime(2026, 1, 1, tzinfo=UTC)
    too_long = settings.max_backtest_range_days + 1

    with pytest.raises(HTTPException) as caught:
        enforce_backtest_range_cap(end_dt - timedelta(days=too_long), end_dt)

    assert caught.value.status_code == 400
    assert caught.value.detail == f"Date range must not exceed {settings.max_backtest_range_days} days (got {too_long})."


def test_a_span_exactly_at_the_cap_is_allowed() -> None:
    end_dt = datetime(2026, 1, 1, tzinfo=UTC)

    enforce_backtest_range_cap(end_dt - timedelta(days=settings.max_backtest_range_days), end_dt)
