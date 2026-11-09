"""`ensure_utc` must actually return UTC — its docstring promised something the code did not do.

FOUND 2026-08-06 while removing a SIM108 finding in `edge_book_cache_ttl_seconds`. That function
normalises with an explicit `if naive: replace(tzinfo=UTC) else: astimezone(UTC)` and then calls
`.replace(hour=..., minute=...)` to find the next daily refresh clock.

The obvious "reuse the SoT helper" cleanup was WRONG: `ensure_utc` attached UTC to naive inputs
but returned already-aware datetimes **unchanged**, so a `+05:00` input came back as `+05:00`
despite a docstring reading "The same datetime with tzinfo=UTC guaranteed".

For comparison and arithmetic that is harmless (same instant). It is NOT harmless for anything
reading wall-clock components — exactly what the cache-TTL function does — where a +05:00
datetime silently yields a refresh boundary five hours off.

Converting is strictly safer than not: it preserves the instant, so it cannot break a correct
call site, and it fixes any that read `.hour`/`.day`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from src.shared.utils.datetime_utils import ensure_utc


def test_naive_is_assumed_utc() -> None:
    """Unchanged behaviour: all producers (Polars, CCXT, ISO strings) intend UTC."""
    naive = datetime(2026, 8, 6, 12, 0)

    result = ensure_utc(naive)

    assert result.tzinfo == UTC
    assert result.hour == 12


def test_aware_non_utc_is_converted_not_passed_through() -> None:
    """THE REGRESSION: a +05:00 datetime used to come back as +05:00."""
    aware = datetime(2026, 8, 6, 12, 0, tzinfo=timezone(timedelta(hours=5)))

    result = ensure_utc(aware)

    assert result.tzinfo == UTC
    assert result.hour == 7, "12:00+05:00 is 07:00Z — wall-clock reads depend on this"


def test_conversion_preserves_the_instant() -> None:
    """Why this change cannot break a correct caller: same moment in time, either way."""
    aware = datetime(2026, 8, 6, 12, 0, tzinfo=timezone(timedelta(hours=-3)))

    assert ensure_utc(aware) == aware


def test_already_utc_is_returned_unchanged() -> None:
    already = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)

    assert ensure_utc(already) == already
    assert ensure_utc(already).hour == 12


def test_is_idempotent() -> None:
    aware = datetime(2026, 8, 6, 12, 0, tzinfo=timezone(timedelta(hours=5)))

    assert ensure_utc(ensure_utc(aware)) == ensure_utc(aware)
