from itertools import pairwise

import pytest

from src.domain.services.position_sizing.kelly import (
    DEFAULT_MAX_POSITION_PCT,
    MIN_SAMPLE_SIZE,
    discrete_kelly_fraction,
    half_kelly,
    heuristic_suggested_position_fraction,
)


class TestHalfKelly:
    """Behavior tests for half-Kelly position sizing."""

    def test_returns_zero_when_not_enough_samples(self) -> None:
        assert half_kelly(win_rate=0.6, avg_win=2.0, avg_loss=1.0, evaluated_signals=10) == 0.0

    def test_returns_zero_at_boundary_minus_one(self) -> None:
        result = half_kelly(win_rate=0.6, avg_win=2.0, avg_loss=1.0, evaluated_signals=MIN_SAMPLE_SIZE - 1)
        assert result == 0.0

    def test_computes_at_exact_min_sample_size(self) -> None:
        result = half_kelly(win_rate=0.6, avg_win=2.0, avg_loss=1.0, evaluated_signals=MIN_SAMPLE_SIZE)
        assert result > 0.0

    def test_applies_hard_cap(self) -> None:
        result = half_kelly(
            win_rate=0.9,
            avg_win=4.0,
            avg_loss=1.0,
            evaluated_signals=100,
            max_position_pct=0.05,
        )
        assert result == 0.05

    def test_uses_default_max_position_pct_when_not_specified(self) -> None:
        result = half_kelly(
            win_rate=0.99,
            avg_win=10.0,
            avg_loss=1.0,
            evaluated_signals=100,
        )
        assert result == DEFAULT_MAX_POSITION_PCT

    def test_handles_basic_formula(self) -> None:
        result = half_kelly(
            win_rate=0.55,
            avg_win=2.0,
            avg_loss=1.0,
            evaluated_signals=100,
            max_position_pct=0.5,
        )
        assert result == pytest.approx(0.1625, abs=1e-4)

    def test_returns_zero_for_negative_expectation(self) -> None:
        result = half_kelly(
            win_rate=0.3,
            avg_win=1.0,
            avg_loss=2.0,
            evaluated_signals=100,
        )
        assert result == 0.0

    def test_returns_zero_for_zero_avg_win(self) -> None:
        assert half_kelly(win_rate=0.6, avg_win=0.0, avg_loss=1.0, evaluated_signals=100) == 0.0

    def test_returns_zero_for_zero_avg_loss(self) -> None:
        assert half_kelly(win_rate=0.6, avg_win=1.0, avg_loss=0.0, evaluated_signals=100) == 0.0

    def test_returns_zero_for_negative_avg_win(self) -> None:
        assert half_kelly(win_rate=0.6, avg_win=-1.0, avg_loss=1.0, evaluated_signals=100) == 0.0

    def test_returns_zero_for_negative_avg_loss(self) -> None:
        assert half_kelly(win_rate=0.6, avg_win=1.0, avg_loss=-1.0, evaluated_signals=100) == 0.0

    def test_clamps_to_zero_when_full_kelly_is_negative(self) -> None:
        result = half_kelly(
            win_rate=0.1,
            avg_win=1.0,
            avg_loss=1.0,
            evaluated_signals=100,
            max_position_pct=0.5,
        )
        assert result == 0.0

    def test_symmetric_payoff_with_even_odds(self) -> None:
        result = half_kelly(
            win_rate=0.5,
            avg_win=1.0,
            avg_loss=1.0,
            evaluated_signals=100,
            max_position_pct=0.5,
        )
        assert result == 0.0


class TestHeuristicSuggestedPositionFraction:
    """API suggested_position_pct: confidence scaled to the max-position cap.

    The fraction scales DEFAULT_MAX_POSITION_PCT by the even-money Kelly edge
    (``clamp(2*confidence - 1, 0, 1)``), so it differentiates across the whole
    confidence range and reaches the cap only at full (100%) confidence. The
    prior ``clamp(confidence - 0.5, 0, cap)`` pinned every confidence >= 55% to
    the cap, so all high-confidence signals showed an identical 5%.
    """

    def test_returns_none_for_non_numeric_confidence(self) -> None:
        assert heuristic_suggested_position_fraction("high") is None  # type: ignore[arg-type]

    def test_returns_none_for_nan(self) -> None:
        assert heuristic_suggested_position_fraction(float("nan")) is None

    def test_coin_flip_confidence_is_zero(self) -> None:
        assert heuristic_suggested_position_fraction(0.5) == 0.0

    def test_below_coin_flip_is_zero(self) -> None:
        assert heuristic_suggested_position_fraction(0.4) == 0.0

    def test_zero_and_negative_confidence_are_zero(self) -> None:
        assert heuristic_suggested_position_fraction(0.0) == 0.0
        assert heuristic_suggested_position_fraction(-0.5) == 0.0

    def test_accepts_integer_confidence(self) -> None:
        assert heuristic_suggested_position_fraction(1) == pytest.approx(DEFAULT_MAX_POSITION_PCT)

    def test_returns_none_for_infinity(self) -> None:
        assert heuristic_suggested_position_fraction(float("inf")) is None

    def test_full_confidence_reaches_cap(self) -> None:
        assert heuristic_suggested_position_fraction(1.0) == pytest.approx(DEFAULT_MAX_POSITION_PCT)

    def test_scales_linearly_with_even_money_edge(self) -> None:
        # f(c) = cap * (2c - 1); at c=0.75 the even-money edge is 0.5 -> half the cap.
        assert heuristic_suggested_position_fraction(0.75) == pytest.approx(DEFAULT_MAX_POSITION_PCT * 0.5)

    def test_high_confidence_no_longer_saturates(self) -> None:
        # Regression: the old clamp(c-0.5, 0, cap) pinned every c >= 0.55 to the
        # cap, so 69% and 76% rendered the identical 5%. They must now differ and
        # both sit below the cap.
        f69 = heuristic_suggested_position_fraction(0.69)
        f76 = heuristic_suggested_position_fraction(0.76)
        assert f69 is not None
        assert f76 is not None
        assert f76 > f69
        assert f69 < DEFAULT_MAX_POSITION_PCT
        assert f76 < DEFAULT_MAX_POSITION_PCT

    def test_monotonic_increasing_in_confidence(self) -> None:
        raw = [heuristic_suggested_position_fraction(c) for c in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]
        assert all(v is not None for v in raw)
        vals = [v for v in raw if v is not None]
        assert all(b > a for a, b in pairwise(vals))

    def test_never_exceeds_cap(self) -> None:
        for c in (0.55, 0.7, 0.9, 1.0, 1.5):
            v = heuristic_suggested_position_fraction(c)
            assert v is not None
            assert 0.0 <= v <= DEFAULT_MAX_POSITION_PCT

    def test_clamps_confidence_above_one(self) -> None:
        assert heuristic_suggested_position_fraction(1.5) == heuristic_suggested_position_fraction(1.0)


def test_the_discrete_kelly_fraction_is_one_formula_for_the_domain_and_the_engine() -> None:
    """BACKTEST-ONE S2b / ONE-DEF: f* = (p*W - q*L) / W -- the half-Kelly here and the engine's kelly sizing both read it."""
    p, win, loss = 0.55, 0.02, 0.015
    f_star = discrete_kelly_fraction(win_rate=p, avg_win=win, avg_loss=loss)

    assert f_star == pytest.approx((p * win - (1 - p) * loss) / win)
    payoff = win / loss  # the engine's spelling: (p*b - q) / b
    assert f_star == pytest.approx((p * payoff - (1 - p)) / payoff)
    assert half_kelly(win_rate=p, avg_win=win, avg_loss=loss, evaluated_signals=40, max_position_pct=1.0) == pytest.approx(f_star / 2)
