"""Behavior tests for the action-anchored Conclusion-line target-price helper.

The Conclusion line shown in the AI-explain modal cites a target price
that must be ACTION-MEANINGFUL (not just the entry price for every action,
which previously made BUY/SELL conclusions misleading). This helper is the
SoT for that computation; both the mock AI provider and any future
target-price display will route through it.

Reference: ``src/domain/services/features/feature_patterns.py`` for the
sign convention of ``dist_to_*_N`` features.
"""

from __future__ import annotations

import pytest

from src.domain.enums import SignalAction
from src.infrastructure.ai.explain_target_price import compute_target_price_for_action


class TestHoldTarget:
    def test_hold_returns_current_price_when_features_present(self) -> None:
        """HOLD has no directional anchor — target = current price even with feature data."""
        target = compute_target_price_for_action(
            SignalAction.HOLD,
            77_400.0,
            {"dist_to_resistance_5": -0.5, "dist_to_support_5": 1.2},
        )
        assert target == pytest.approx(77_400.0)

    def test_hold_returns_current_price_with_none_features(self) -> None:
        target = compute_target_price_for_action(SignalAction.HOLD, 77_400.0, None)
        assert target == pytest.approx(77_400.0)

    def test_hold_accepts_string_action(self) -> None:
        """Mock provider passes a raw string in some legacy paths — must work."""
        target = compute_target_price_for_action("HOLD", 77_400.0, None)
        assert target == pytest.approx(77_400.0)


class TestBuyTarget:
    def test_buy_uses_5_bar_resistance_distance(self) -> None:
        """BUY target = current * (1 + |dist_to_resistance_5|/100). 5-bar wins over 20-bar."""
        target = compute_target_price_for_action(
            SignalAction.BUY,
            77_400.0,
            {"dist_to_resistance_5": -0.42, "dist_to_resistance_20": -1.5},
        )
        # 77_400 * (1 + 0.42/100) = 77_400 * 1.0042 = 77_725.08
        assert target == pytest.approx(77_725.08, rel=1e-4)

    def test_buy_falls_through_to_20_bar_when_5_bar_missing(self) -> None:
        """Defensive: short-window feature missing → use longer window."""
        target = compute_target_price_for_action(
            SignalAction.BUY,
            77_400.0,
            {"dist_to_resistance_20": -1.0},
        )
        # 77_400 * 1.01 = 78_174
        assert target == pytest.approx(78_174.0, rel=1e-4)

    def test_buy_falls_through_to_20_bar_when_5_bar_is_zero(self) -> None:
        """Zero distance is not informative — fall through to next key."""
        target = compute_target_price_for_action(
            SignalAction.BUY,
            77_400.0,
            {"dist_to_resistance_5": 0.0, "dist_to_resistance_20": -0.5},
        )
        # 77_400 * 1.005 = 77_787
        assert target == pytest.approx(77_787.0, rel=1e-4)

    def test_buy_takes_absolute_value_when_dist_is_positive(self) -> None:
        """Sign convention isn't enforced upstream — be robust to either sign.

        ``dist_to_resistance_N`` is typically NEGATIVE (price below resistance)
        per ``feature_patterns.py``, but we ``abs(...)`` anyway so a future
        change to the sign convention doesn't silently flip our targets.
        """
        target = compute_target_price_for_action(
            SignalAction.BUY,
            77_400.0,
            {"dist_to_resistance_5": 0.42},
        )
        assert target == pytest.approx(77_725.08, rel=1e-4)

    def test_buy_returns_current_when_features_empty(self) -> None:
        """No data → fall back to current price (never crash)."""
        target = compute_target_price_for_action(SignalAction.BUY, 77_400.0, {})
        assert target == pytest.approx(77_400.0)

    def test_buy_returns_current_when_features_are_none(self) -> None:
        target = compute_target_price_for_action(SignalAction.BUY, 77_400.0, None)
        assert target == pytest.approx(77_400.0)

    def test_buy_ignores_non_numeric_feature_values(self) -> None:
        """A None / string / NaN in the feature dict must NOT crash."""
        target = compute_target_price_for_action(
            SignalAction.BUY,
            77_400.0,
            {"dist_to_resistance_5": None, "dist_to_resistance_20": "n/a"},
        )
        assert target == pytest.approx(77_400.0)

    def test_buy_ignores_non_finite_feature_values(self) -> None:
        """Inf / NaN must NOT crash."""
        target = compute_target_price_for_action(
            SignalAction.BUY,
            77_400.0,
            {"dist_to_resistance_5": float("inf"), "dist_to_resistance_20": float("nan")},
        )
        assert target == pytest.approx(77_400.0)


class TestSellTarget:
    def test_sell_uses_5_bar_support_distance(self) -> None:
        """SELL target = current * (1 - |dist_to_support_5|/100). Below current price."""
        target = compute_target_price_for_action(
            SignalAction.SELL,
            77_400.0,
            {"dist_to_support_5": 1.18},
        )
        # 77_400 * (1 - 1.18/100) = 77_400 * 0.9882 = 76_487.32
        assert target == pytest.approx(76_487.32, rel=1e-4)

    def test_sell_falls_through_to_20_bar_when_5_bar_missing(self) -> None:
        target = compute_target_price_for_action(
            SignalAction.SELL,
            77_400.0,
            {"dist_to_support_20": 2.0},
        )
        assert target == pytest.approx(75_852.0, rel=1e-4)


class TestDefensive:
    def test_zero_price_returns_zero(self) -> None:
        """Defensive: a zero/negative input must NOT yield negative targets."""
        target = compute_target_price_for_action(SignalAction.BUY, 0.0, {"dist_to_resistance_5": -0.5})
        assert target == pytest.approx(0.0)

    def test_negative_price_returns_zero(self) -> None:
        """Defensive: a negative input must NOT yield a negative target."""
        target = compute_target_price_for_action(SignalAction.BUY, -100.0, {"dist_to_resistance_5": -0.5})
        assert target == pytest.approx(0.0)

    def test_unknown_action_string_returns_current(self) -> None:
        """An unknown action (future / typo) must degrade to HOLD-style."""
        target = compute_target_price_for_action("LONG_LEVERAGED", 77_400.0, {"dist_to_resistance_5": -0.5})
        assert target == pytest.approx(77_400.0)
