"""The holdout a run reserves is DERIVED from what the cert will need — on EVERY timeframe.

MEASURED 2026-09-18, which is why this exists. Two twins of one family, same cutoff rule,
different timeframes:

    1d  v42     473 unseen days ->  71 confirm trades -> thin, unmeasurable
    4h  v411  1,205 unseen days -> 738 confirm trades -> measurable (and it failed, honestly)

`automated_retrain_data_end` sizes the window by `ARENA_BACKTEST_MIN_ROWS`, which answers "can this
be backtested at all". A cert asks a harder question: can a SELECT window rank the levers AND a
disjoint CONFIRM window carry enough trades for its Sharpe to mean anything (MinTRL)? A holdout
sized for the first question produces books the second can only call `unmeasured`.

The bands are IMPORTED from the registry, never typed out: membership is a `band` field on
`TimeframeDefinition`, so a new timeframe joins these tests by existing rather than by someone
remembering to add it (`.claude/rules/full-htf-grid-always.md`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.services.edge_lifecycle.gate import MIN_TRADES_FOR_SHARPE
from src.domain.services.training_holdout_policy import (
    CERT_SELECT_SHARE_OF_CONFIRM,
    DATA_END_FORMAT,
    automated_retrain_data_end,
    cert_ready_data_end,
    cert_ready_holdout_days,
    expected_confirm_trades,
    has_holdout_decision,
    parse_data_end_cutoff,
    provable_per_trade_sharpe,
)
from src.shared.constants.timeframe_bands import HIGHER_TIMEFRAMES, LOWER_TIMEFRAMES
from src.shared.constants.timeframes import bars_per_day

NOW = datetime(2026, 9, 18, tzinfo=UTC)

#: Every timeframe the product trains or certifies on, slowest-to-fastest order derived from the
#: registry itself. A hand-written list is exactly the drift this rule exists to prevent.
ALL_BANDS: tuple[str, ...] = tuple(LOWER_TIMEFRAMES) + tuple(HIGHER_TIMEFRAMES)


@pytest.mark.parametrize("timeframe", ALL_BANDS)
class TestEveryTimeframeGetsAWindowThatBuysTheMeasurement:
    def test_the_window_is_positive_and_finite(self, timeframe: str) -> None:
        days = cert_ready_holdout_days(timeframe)
        assert days > 0
        assert days < 100 * 365, f"{timeframe} would reserve longer than any market history"

    def test_the_confirm_half_clears_the_gate_that_decides_measurability(self, timeframe: str) -> None:
        """The property the function exists for, computed independently of its implementation.

        Sized against `MIN_TRADES_FOR_SHARPE` — the grader's own floor — rather than MinTRL, for a
        measured reason recorded in the policy: proving an annualised Sharpe of 1.0 costs ~5,900
        trades, which is 9,817 days on 4h and 58,900 on 1d. A window nobody can build is not a
        policy.
        """
        confirm_days = cert_ready_holdout_days(timeframe) / (1.0 + CERT_SELECT_SHARE_OF_CONFIRM)
        confirm_bars = confirm_days * bars_per_day(timeframe)
        assert expected_confirm_trades(confirm_bars) >= MIN_TRADES_FOR_SHARPE

    def test_the_window_discloses_what_it_could_actually_prove(self, timeframe: str) -> None:
        """The gap stays visible: a book weaker than this cannot be established on this window."""
        provable = provable_per_trade_sharpe(timeframe)
        assert provable is not None
        assert provable > 0.0

    def test_it_never_reserves_less_than_the_backtestable_floor(self, timeframe: str) -> None:
        """Never narrower than the old rule. Equal only where the 7-day RECENCY floor binds.

        Measured: on `5m` both rules land on `HOLDOUT_MIN_DAYS`, because 100 trades of 5m candles
        is about three days and the floor is what stops a "holdout" being a weekend. Asserting
        STRICTLY wider everywhere would have been a claim the arithmetic does not make.
        """
        assert cert_ready_data_end(timeframe, now=NOW) <= automated_retrain_data_end(timeframe, now=NOW)

    def test_the_cutoff_is_a_usable_holdout_decision(self, timeframe: str) -> None:
        cutoff = cert_ready_data_end(timeframe, now=NOW)
        assert has_holdout_decision(data_end=cutoff, no_holdout=False)
        parsed = parse_data_end_cutoff(cutoff)
        assert parsed is not None
        assert parsed < NOW

    def test_the_cutoff_is_now_minus_the_reserved_days(self, timeframe: str) -> None:
        expected = (NOW - timedelta(days=cert_ready_holdout_days(timeframe))).strftime(DATA_END_FORMAT)
        assert cert_ready_data_end(timeframe, now=NOW) == expected


class TestTheWindowScalesWithTheTimeframe:
    def test_a_faster_timeframe_never_needs_more_calendar_days(self) -> None:
        """Monotone across the whole ordered set: more bars per day can only shorten the window."""
        ordered = sorted(ALL_BANDS, key=bars_per_day, reverse=True)
        days = [cert_ready_holdout_days(timeframe) for timeframe in ordered]
        assert days == sorted(days), dict(zip(ordered, days, strict=True))

    def test_the_fastest_and_slowest_differ_by_more_than_rounding(self) -> None:
        fastest = max(ALL_BANDS, key=bars_per_day)
        slowest = min(ALL_BANDS, key=bars_per_day)
        assert cert_ready_holdout_days(slowest) > cert_ready_holdout_days(fastest) * 10

    def test_an_unknown_timeframe_raises_rather_than_guessing(self) -> None:
        with pytest.raises(ValueError, match="3h"):
            cert_ready_holdout_days("3h")

    def test_the_scan_is_not_vacuous(self) -> None:
        """Fails if the bands stop resolving — a parametrised suite over an empty set reports green."""
        assert len(ALL_BANDS) >= 10
