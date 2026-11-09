"""Behavior tests: backtest API date-only strings map to inclusive UTC day bounds."""

from datetime import UTC, datetime, timedelta

from src.shared.utils.datetime_utils import (
    parse_backtest_range_end_utc,
    parse_backtest_range_start_utc,
    parse_datetime_utc,
)


def test_calendar_start_date_is_start_of_utc_day() -> None:
    assert parse_backtest_range_start_utc("2026-04-11") == datetime(2026, 4, 11, 0, 0, 0, 0, tzinfo=UTC)


def test_calendar_start_strips_whitespace() -> None:
    assert parse_backtest_range_start_utc("  2026-04-11  ") == parse_datetime_utc("2026-04-11")


def test_calendar_end_date_is_end_of_utc_day_inclusive() -> None:
    end = parse_backtest_range_end_utc("2026-04-11")
    assert end == datetime(2026, 4, 11, 23, 59, 59, 999999, tzinfo=UTC)


def test_calendar_end_strips_whitespace() -> None:
    assert parse_backtest_range_end_utc("  2026-01-02  ") == parse_backtest_range_end_utc("2026-01-02")


def test_explicit_iso_datetime_end_unchanged_semantics() -> None:
    """Strings with a time component use parse_datetime_utc (parity with scripts / power users)."""
    raw = "2026-04-11T21:30:00+00:00"
    assert parse_backtest_range_end_utc(raw) == parse_datetime_utc(raw)


def test_explicit_iso_datetime_start_unchanged_semantics() -> None:
    raw = "2026-04-11T08:00:00"
    assert parse_backtest_range_start_utc(raw) == parse_datetime_utc(raw.strip())


def test_same_calendar_day_range_is_ordered() -> None:
    """Regression: date-only same start/end must not collapse to an empty invalid range."""
    start = parse_backtest_range_start_utc("2026-04-11")
    end = parse_backtest_range_end_utc("2026-04-11")
    assert start < end
    assert end - start > timedelta(hours=23)
