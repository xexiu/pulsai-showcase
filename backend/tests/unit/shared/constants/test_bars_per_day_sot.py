"""`bars_per_day` was implemented three times, from three authorities, and two disagreed.

REUSE-AUDIT: `get_timeframe_delta` / `TIMEFRAME_REGISTRY` (reused as the authority);
`BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME` (rejected as the authority -- it stores rounded integers,
which is the defect measured below); `backtest_annualization_factor` (a different quantity: bars
per YEAR for annualising, not bars per day for window sizing).

MEASURED 2026-08-15 across the full research grid:

      tf    registry     ppy/365        ccxt   agree?
      4h      6.0000      6.0000      6.0000   yes
      1d      1.0000      1.0000      1.0000   yes
      3d      0.3333      0.3342      0.3333   NO
      1w      0.1429      0.1425      0.1429   NO

Two of the three implementations claimed IN THEIR OWN DOCSTRING to be the single source of truth
("SoT: TIMEFRAME_REGISTRY, never a hardcoded map" and "from the periods-per-year SoT (reuse, no
hardcoded per-TF counts)"). Both were sincere and one was wrong, which is the whole argument for
checking a docstring against the running system instead of reading it as evidence.

0.3% is small, and that is precisely why it survived: it is invisible until a 3d window computed
by one path is compared against the same window computed by the other, and then it reads as a
data problem rather than as two functions answering the same question differently.
"""

from __future__ import annotations

import pytest

from src.shared.constants.backtest_timeframe import BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME
from src.shared.constants.hunt_timeframes import RESEARCH_HIGH_TIMEFRAMES, RESEARCH_LOW_TIMEFRAMES
from src.shared.constants.timeframes import TIMEFRAME_REGISTRY, bars_per_day

_DAYS_PER_YEAR = 365.0


class TestTheValuesThemselves:
    @pytest.mark.parametrize(
        ("timeframe", "expected"),
        [("1d", 1.0), ("12h", 2.0), ("8h", 3.0), ("6h", 4.0), ("4h", 6.0), ("1h", 24.0), ("5m", 288.0)],
    )
    def test_whole_ratios_are_exact(self, timeframe: str, expected: float) -> None:
        assert bars_per_day(timeframe) == expected

    def test_multi_day_timeframes_are_the_true_ratio_not_the_rounded_one(self) -> None:
        """THE DEFECT: `122 / 365 = 0.334247`, but a 3d bar is exactly one third of a day."""
        assert bars_per_day("3d") == pytest.approx(1 / 3)
        assert bars_per_day("1w") == pytest.approx(1 / 7)

    def test_it_disagrees_with_the_periods_per_year_round_trip_where_that_round_trip_is_wrong(self) -> None:
        """Pins the defect rather than describing it: if the table is ever fixed this still holds,
        and if someone re-routes `bars_per_day` back through it, this fails."""
        for timeframe in ("3d", "1w"):
            rounded = BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME[timeframe] / _DAYS_PER_YEAR

            assert bars_per_day(timeframe) != pytest.approx(rounded, abs=1e-9), timeframe

    def test_intraday_timeframes_never_disagreed_and_still_do_not(self) -> None:
        """The migration must move no intraday number — those were correct in all three."""
        for timeframe in RESEARCH_LOW_TIMEFRAMES:
            rounded = BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME[timeframe] / _DAYS_PER_YEAR

            assert bars_per_day(timeframe) == pytest.approx(rounded), timeframe


class TestItAnswersForTheWholeGrid:
    def test_every_research_timeframe_resolves(self) -> None:
        for timeframe in (*RESEARCH_LOW_TIMEFRAMES, *RESEARCH_HIGH_TIMEFRAMES):
            assert bars_per_day(timeframe) > 0, timeframe

    def test_every_registered_timeframe_resolves(self) -> None:
        for timeframe in TIMEFRAME_REGISTRY:
            assert bars_per_day(timeframe) > 0, timeframe

    def test_it_is_monotonically_decreasing_in_bar_length(self) -> None:
        resolved = [bars_per_day(tf) for tf in ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w")]

        assert resolved == sorted(resolved, reverse=True), resolved


class TestAnUnknownTimeframeRaises:
    """A silent per-timeframe default is what makes this class of drift invisible.

    The old hunt-loop copy used `.get(tf, DEFAULT_BACKTEST_PERIODS_PER_YEAR)`, so an unlisted
    timeframe quietly returned the DEFAULT's bars-per-day and every window built from it was
    wrong by whatever the gap happened to be — with no error anywhere.
    """

    def test_nonsense_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            bars_per_day("4x")

    def test_case_and_whitespace_are_tolerated_because_callers_pass_user_strings(self) -> None:
        assert bars_per_day(" 4H ") == 6.0
