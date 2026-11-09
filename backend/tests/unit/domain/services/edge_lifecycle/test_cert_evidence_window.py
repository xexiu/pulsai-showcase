"""Is a cert's window long enough for its number to MEAN anything?

MEASURED GAP (2026-08-12). The corpus screens trade COUNT (`MIN_TRADES_FOR_SHARPE`) but has no
window-LENGTH floor anywhere. Across the 33 certs on disk, **16 have windows under 30 days**:

    1h  gb_clf v25, 1h lightgbm v26, 4h gb_clf v393, 4h sgd v2    2 DAYS
    1d  hist_gb v3                                                3 days
    12h ridge v8/v9, 1d lightgbm v31/v33                          6 days
    1d  gb_clf v2  (THE LIVE PRODUCTION MODEL)                    25 days

Their `beats B&H` ratios (1.00x-1.10x) were ranked in the same table as a 587-day book's 2.47x,
as though the two claims were comparable. They are not.

WHY THIS IS NOT A KILL. A 2-day window says nothing about the MODEL -- it says the CERT is
uninformative. Reporting "excluded" would repeat the exact error corrected twice today (v15's
missing `capital_modes` read as a verdict; v42's unrecorded levers read as ruin). Missing evidence
is owed a MEASUREMENT, not a tombstone, so `is_sufficient` is None when unknown and the state is
`window_too_short`, never `failed`.

WHY BARS AND NOT DAYS. The owner asked earlier whether the significance floor should be
timeframe-aware ("5m is not the same as 12h... or inventing 100 magic number?"). Measuring the
window in BARS of its own timeframe makes it so by construction, and derives the threshold from
`MIN_TRADES_FOR_SHARPE` rather than inventing a second number: with sequential positions a book
cannot take more trades than it has bars, so a window shorter than the trade floor cannot reach
that floor by that route.

    1d  -> 100 bars = 100 days       4h -> 100 bars ~ 16.7 days
    12h -> 100 bars =  50 days       1h -> 100 bars ~  4.2 days

HONEST LIMIT, stated rather than hidden: with `max_open_positions = N` up to N trades can open per
bar, so the bound is not strict -- a 50-concurrency book could book 100 trades across 2 bars. But
those are 100 OVERLAPPING bets on two bars of price action, which is one observation wearing a
hundred hats: weaker evidence, not stronger. The bars floor is the right shape either way.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.services.edge_lifecycle.cert_evidence_window import (
    MIN_WINDOW_BARS,
    WINDOW_SUFFICIENT,
    WINDOW_TOO_SHORT,
    WINDOW_UNKNOWN,
    assess_window_evidence,
    window_bars,
)


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


class TestWindowBars:
    """A span is converted into bars OF ITS OWN TIMEFRAME -- that is what makes it comparable."""

    @pytest.mark.parametrize(
        ("timeframe", "start", "end", "expected"),
        [
            ("1d", "2025-01-01", "2025-04-11", 100.0),
            ("12h", "2025-01-01", "2025-02-20", 100.0),
            ("4h", "2025-01-01", "2025-01-02", 6.0),
            ("1h", "2025-01-01", "2025-01-02", 24.0),
        ],
    )
    def test_a_span_becomes_bars_of_that_timeframe(self, timeframe: str, start: str, end: str, expected: float) -> None:
        assert window_bars(start=_dt(start), end=_dt(end), timeframe=timeframe) == pytest.approx(expected)

    def test_the_same_span_is_far_more_bars_on_a_faster_timeframe(self) -> None:
        """The whole point: 26 days is noise on 1d and a real sample on 1h."""
        start, end = _dt("2025-01-01"), _dt("2025-01-27")

        daily = window_bars(start=start, end=end, timeframe="1d")
        hourly = window_bars(start=start, end=end, timeframe="1h")

        assert daily == pytest.approx(26.0)
        assert hourly == pytest.approx(624.0)

    def test_an_inverted_or_empty_span_is_zero_not_negative(self) -> None:
        assert window_bars(start=_dt("2025-06-01"), end=_dt("2025-01-01"), timeframe="1d") == 0.0
        assert window_bars(start=_dt("2025-01-01"), end=_dt("2025-01-01"), timeframe="1d") == 0.0

    def test_an_unknown_timeframe_yields_none_rather_than_a_guess(self) -> None:
        assert window_bars(start=_dt("2025-01-01"), end=_dt("2025-06-01"), timeframe="7s") is None

    def test_a_missing_endpoint_yields_none(self) -> None:
        assert window_bars(start=None, end=_dt("2025-06-01"), timeframe="1d") is None
        assert window_bars(start=_dt("2025-01-01"), end=None, timeframe="1d") is None


class TestAssessWindowEvidence:
    def test_a_long_out_of_sample_window_is_sufficient(self) -> None:
        """`1d gb_clf v10`: 2024-12-31 -> 2026-08-10, 587 days. Real evidence."""
        got = assess_window_evidence(start=_dt("2024-12-31"), end=_dt("2026-08-10"), timeframe="1d")

        assert got.state == WINDOW_SUFFICIENT
        assert got.is_sufficient is True
        assert got.bars is not None
        assert got.bars > MIN_WINDOW_BARS

    def test_the_two_day_certs_are_reported_as_too_short(self) -> None:
        """`1h gb_clf v25` and `4h gb_clf v393` both ran 2 days and printed a 1.00x ratio."""
        four_hour = assess_window_evidence(start=_dt("2026-08-08"), end=_dt("2026-08-10"), timeframe="4h")

        assert four_hour.state == WINDOW_TOO_SHORT
        assert four_hour.is_sufficient is False
        assert four_hour.bars == pytest.approx(12.0)
        assert four_hour.required_bars == MIN_WINDOW_BARS

    def test_the_live_production_model_window_is_too_short(self) -> None:
        """`1d gb_clf v2` -- 25 days, against a 100-bar floor. The model users trade on.

        Not a verdict on v2: its cert is uninformative, so v2 is owed a re-cert on a real window.
        """
        got = assess_window_evidence(start=_dt("2026-07-16"), end=_dt("2026-08-10"), timeframe="1d")

        assert got.state == WINDOW_TOO_SHORT
        assert got.bars == pytest.approx(25.0)

    def test_the_same_25_day_span_is_sufficient_on_1h(self) -> None:
        """Timeframe-aware by construction, not by a second hand-picked threshold."""
        got = assess_window_evidence(start=_dt("2026-07-16"), end=_dt("2026-08-10"), timeframe="1h")

        assert got.state == WINDOW_SUFFICIENT
        assert got.is_sufficient is True

    def test_unknown_is_none_and_never_false(self) -> None:
        """ "We cannot tell" and "provably too short" are different findings.

        Collapsing them is how an UNMEASURED book gets recorded as a FAILED one -- the error
        corrected twice on 2026-08-12 (v15's absent capital_modes, v42's absent levers).
        """
        got = assess_window_evidence(start=None, end=_dt("2026-08-10"), timeframe="1d")

        assert got.state == WINDOW_UNKNOWN
        assert got.is_sufficient is None
        assert got.is_sufficient is not False

    def test_an_unknown_timeframe_is_unknown_not_short(self) -> None:
        got = assess_window_evidence(start=_dt("2020-01-01"), end=_dt("2026-01-01"), timeframe="nonsense")

        assert got.state == WINDOW_UNKNOWN
        assert got.is_sufficient is None

    def test_it_carries_the_numbers_a_reader_needs_to_judge_it(self) -> None:
        """A state with no measurement behind it is the assertion this repo keeps paying for."""
        got = assess_window_evidence(start=_dt("2026-08-08"), end=_dt("2026-08-10"), timeframe="1d")

        assert got.timeframe == "1d"
        assert got.span_days == pytest.approx(2.0)
        assert got.bars == pytest.approx(2.0)
        assert got.required_bars == MIN_WINDOW_BARS

    def test_the_floor_is_inclusive_at_the_boundary(self) -> None:
        """Exactly at the floor passes -- the floor is a minimum, not a strict inequality."""
        got = assess_window_evidence(start=_dt("2025-01-01"), end=_dt("2025-04-11"), timeframe="1d")

        assert got.bars == pytest.approx(float(MIN_WINDOW_BARS))
        assert got.is_sufficient is True


class TestTheFloorIsDerivedNotInvented:
    def test_it_reuses_the_existing_significance_floor(self) -> None:
        """MIN_WINDOW_BARS must stay tied to MIN_TRADES_FOR_SHARPE, not drift into a 2nd number.

        `MIN_TRADES_FOR_SHARPE = 100` was itself calibrated from one anecdote. Deriving from it
        does not launder that, but it does refuse to ADD a second unsourced constant -- and it
        keeps one knob to fix when the floor is put on a proper footing.
        """
        from src.domain.services.edge_lifecycle.gate import MIN_TRADES_FOR_SHARPE

        assert MIN_WINDOW_BARS == MIN_TRADES_FOR_SHARPE
