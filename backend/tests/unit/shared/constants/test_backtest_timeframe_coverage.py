"""Backtest per-timeframe maps cover the registry, and deriving them changed no existing value.

WHY THIS EXISTS. `BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME` and
`BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME` were hand-typed dicts. They silently lost 2h and 6h when
the registry gained them, and a MISSING annualization divisor does not crash: the caller falls
back to `DEFAULT_BACKTEST_PERIODS_PER_YEAR`, which is the 1h value. A 6h book's Sharpe would have
been annualized as though it traded six times as often — a wrong number with no error anywhere.

They are now derived from `TIMEFRAME_MS`. Deriving a table that already shipped is only safe if it
reproduces every previous entry EXACTLY, so the pre-existing literals are pinned below verbatim.
If a future edit changes one, this fails rather than quietly re-pricing every historical backtest.
"""

from __future__ import annotations

import pytest

from src.shared.constants.backtest_timeframe import (
    BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME,
    BACKTEST_HIGH_FREQUENCY_TRADES_PER_DAY_THRESHOLD,
    BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME,
)
from src.shared.constants.timeframes import TIMEFRAME_REGISTRY, VALID_TIMEFRAMES_SIGNAL_AND_TRAINING

#: The literals these maps held before derivation (commit cd7d7dd82 and earlier), copied verbatim.
_PERIODS_PER_YEAR_BEFORE = {
    "1m": 525_600,
    "5m": 105_120,
    "15m": 35_040,
    "30m": 17_520,
    "1h": 8_760,
    "4h": 2_190,
    "8h": 1_095,
    "12h": 730,
    "1d": 365,
    "3d": 122,
    "1w": 52,
}

_CANDLES_PER_DAY_BEFORE = {
    "1m": 1_440,
    "5m": 288,
    "15m": 96,
    "30m": 48,
    "1h": 24,
    "4h": 6,
    "8h": 3,
    "12h": 2,
    "1d": 1,
    "3d": 1,
    "1w": 1,
}


class TestDerivingChangedNoExistingValue:
    @pytest.mark.parametrize(("timeframe", "expected"), sorted(_PERIODS_PER_YEAR_BEFORE.items()))
    def test_periods_per_year_matches_the_previous_literal(self, timeframe: str, expected: int) -> None:
        assert BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME[timeframe] == expected

    @pytest.mark.parametrize(("timeframe", "expected"), sorted(_CANDLES_PER_DAY_BEFORE.items()))
    def test_candles_per_day_matches_the_previous_literal(self, timeframe: str, expected: int) -> None:
        assert BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME[timeframe] == expected


class TestTheMapsCoverTheRegistry:
    @pytest.mark.parametrize("timeframe", sorted(TIMEFRAME_REGISTRY))
    def test_every_registry_timeframe_has_an_annualization_divisor(self, timeframe: str) -> None:
        assert timeframe in BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME

    @pytest.mark.parametrize("timeframe", sorted(TIMEFRAME_REGISTRY))
    def test_every_registry_timeframe_has_candles_per_day(self, timeframe: str) -> None:
        assert BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME[timeframe] >= 1

    @pytest.mark.parametrize("timeframe", sorted(VALID_TIMEFRAMES_SIGNAL_AND_TRAINING))
    def test_every_tradable_timeframe_has_a_high_frequency_threshold(self, timeframe: str) -> None:
        """Product tuning, so it is a literal — but it must still cover what we trade."""
        assert timeframe in BACKTEST_HIGH_FREQUENCY_TRADES_PER_DAY_THRESHOLD


class TestTheNewTimeframesGotRealValues:
    def test_2h_and_6h_annualize_correctly(self) -> None:
        """8,760 hourly bars a year: 2h halves it, 6h is a sixth."""
        assert BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME["2h"] == 4_380
        assert BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME["6h"] == 1_460

    def test_2h_and_6h_candles_per_day(self) -> None:
        assert BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME["2h"] == 12
        assert BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME["6h"] == 4

    def test_the_thresholds_stay_monotone_in_bar_length(self) -> None:
        """A longer bar can never tolerate MORE trades per day than a shorter one."""
        ladder = ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d")
        values = [BACKTEST_HIGH_FREQUENCY_TRADES_PER_DAY_THRESHOLD[tf] for tf in ladder]

        assert values == sorted(values, reverse=True), dict(zip(ladder, values, strict=True))
