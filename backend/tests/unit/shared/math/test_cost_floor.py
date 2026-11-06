"""Behavior tests for the break-even-AUC cost floor.

These guard the analytic ceiling that says "no directional classifier at AUC X
nets positive over hold H at cost C". They assert the *behaviour* (monotonicity,
boundary cases, the binormal AUC↔accuracy bridge), not just the algebra.
"""

from __future__ import annotations

import math

import pytest
from scipy.stats import norm  # test-only ground truth

from src.shared.math.cost_floor import (
    UNACHIEVABLE_BREAK_EVEN_AUC,
    auc_to_directional_accuracy,
    break_even_auc,
    directional_accuracy_to_auc,
    expected_absolute_move,
    expected_net_edge_per_trade,
    round_trip_cost_fraction,
)

# --------------------------------------------------------------------------- #
# AUC ↔ directional accuracy (binormal bridge)
# --------------------------------------------------------------------------- #


def test_auc_half_is_accuracy_half() -> None:
    assert auc_to_directional_accuracy(0.5) == pytest.approx(0.5, abs=1e-12)


def test_accuracy_strictly_increases_with_auc() -> None:
    assert auc_to_directional_accuracy(0.55) < auc_to_directional_accuracy(0.6) < auc_to_directional_accuracy(0.7)


def test_auc_058_matches_binormal_reference() -> None:
    """AUC 0.58 → ACC = Φ(Φ⁻¹(0.58)/√2) ≈ 0.5568 (scipy ground truth)."""
    expected = float(norm.cdf(norm.ppf(0.58) / math.sqrt(2.0)))
    assert auc_to_directional_accuracy(0.58) == pytest.approx(expected, abs=1e-7)
    assert auc_to_directional_accuracy(0.58) == pytest.approx(0.5568, abs=1e-3)


@pytest.mark.parametrize("auc", [0.51, 0.55, 0.6, 0.72, 0.9])
def test_auc_accuracy_roundtrip(auc: float) -> None:
    acc = auc_to_directional_accuracy(auc)
    assert directional_accuracy_to_auc(acc) == pytest.approx(auc, abs=1e-7)


@pytest.mark.parametrize("auc", [-0.1, 0.0, 1.0, 1.2])
def test_auc_to_accuracy_rejects_out_of_range(auc: float) -> None:
    with pytest.raises(ValueError, match="auc must be in"):
        auc_to_directional_accuracy(auc)


# --------------------------------------------------------------------------- #
# Expected absolute move
# --------------------------------------------------------------------------- #


def test_expected_move_scales_with_sqrt_holding() -> None:
    one = expected_absolute_move(0.01, 1.0)
    four = expected_absolute_move(0.01, 4.0)
    assert four == pytest.approx(2.0 * one, rel=1e-9)  # √4 = 2


def test_expected_move_scales_linearly_with_sigma() -> None:
    base = expected_absolute_move(0.01, 9.0)
    assert expected_absolute_move(0.02, 9.0) == pytest.approx(2.0 * base, rel=1e-9)


def test_expected_move_rejects_nonpositive_holding() -> None:
    with pytest.raises(ValueError, match="holding_bars must be positive"):
        expected_absolute_move(0.01, 0.0)


# --------------------------------------------------------------------------- #
# Round-trip cost
# --------------------------------------------------------------------------- #


def test_round_trip_cost_is_twice_fee_plus_slippage() -> None:
    # Binance taker 0.10% + slippage 0.03% → round trip 0.26%.
    assert round_trip_cost_fraction(0.001, 0.0003) == pytest.approx(0.0026, abs=1e-12)


def test_round_trip_cost_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        round_trip_cost_fraction(-0.001, 0.0003)


# --------------------------------------------------------------------------- #
# Break-even AUC — the cost floor
# --------------------------------------------------------------------------- #


def test_break_even_auc_zero_cost_is_half() -> None:
    """No cost → any edge above coin-flip clears."""
    assert break_even_auc(sigma_bar=0.01, holding_bars=10.0, round_trip_cost=0.0) == pytest.approx(0.5, abs=1e-9)


def test_break_even_auc_decreases_with_longer_hold() -> None:
    """A longer hold grows the move scale vs the fixed round-trip cost → lower bar."""
    short = break_even_auc(sigma_bar=0.01, holding_bars=4.0, round_trip_cost=0.0026)
    long = break_even_auc(sigma_bar=0.01, holding_bars=64.0, round_trip_cost=0.0026)
    assert long < short


def test_break_even_auc_increases_with_cost() -> None:
    cheap = break_even_auc(sigma_bar=0.01, holding_bars=24.0, round_trip_cost=0.001)
    dear = break_even_auc(sigma_bar=0.01, holding_bars=24.0, round_trip_cost=0.006)
    assert dear > cheap


def test_break_even_auc_unachievable_when_cost_dominates() -> None:
    """Tiny move vs huge cost → even a perfect caller can't break even (returns 1.0)."""
    floor = break_even_auc(sigma_bar=0.0005, holding_bars=1.0, round_trip_cost=0.02)
    assert floor == UNACHIEVABLE_BREAK_EVEN_AUC


def test_break_even_auc_is_a_valid_probability_when_achievable() -> None:
    floor = break_even_auc(sigma_bar=0.01, holding_bars=12.0, round_trip_cost=0.0026)
    assert 0.5 < floor < 1.0


def test_net_edge_negative_below_break_even_positive_above() -> None:
    """The break-even AUC is exactly the sign-flip point of expected net edge."""
    sigma, hold, cost = 0.01, 12.0, 0.0026
    floor = break_even_auc(sigma_bar=sigma, holding_bars=hold, round_trip_cost=cost)
    below = expected_net_edge_per_trade(auc=floor - 0.02, sigma_bar=sigma, holding_bars=hold, round_trip_cost=cost)
    above = expected_net_edge_per_trade(auc=floor + 0.02, sigma_bar=sigma, holding_bars=hold, round_trip_cost=cost)
    assert below < 0.0 < above


def test_net_edge_at_break_even_is_approximately_zero() -> None:
    sigma, hold, cost = 0.012, 18.0, 0.0026
    floor = break_even_auc(sigma_bar=sigma, holding_bars=hold, round_trip_cost=cost)
    assert expected_net_edge_per_trade(auc=floor, sigma_bar=sigma, holding_bars=hold, round_trip_cost=cost) == pytest.approx(0.0, abs=1e-9)
