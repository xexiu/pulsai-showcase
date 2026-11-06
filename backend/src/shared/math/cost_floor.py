"""Break-even-AUC cost floor (SoT) — the analytic ceiling for directional ML.

WHY this module exists:
A directional classifier only nets positive if its per-trade edge clears the
round-trip trading cost. This module turns that into a closed form: given the
per-bar return volatility, the holding period (which sets both the move scale and
the turnover) and the round-trip cost, it computes the MINIMUM ROC-AUC a balanced
binary classifier must reach to break even after costs. If the realistically
achievable AUC sits below that floor for every tradeable holding period, the
directional track is dead BEFORE any model is trained — no label, feature, or
architecture choice can rescue it. The empirical 603-cell exhaustive sweep
(``artifacts/oos_hunt/FINDINGS_EXHAUSTIVE_SEARCH.md``) is the evidence; this is
the proof.

Model (binormal, equal-variance — standard ROC theory):
- A classifier with separation d (score-std units) has AUC = Φ(d/√2) and
  optimal-threshold balanced accuracy ACC = Φ(d/2); eliminating d gives
  ACC = Φ(Φ⁻¹(AUC)/√2)  and inversely  AUC = Φ(√2·Φ⁻¹(ACC)).
- Over an H-bar hold the |move| scale is E|R_H| = sigma_bar·√H·√(2/π)
  (mean absolute value of a zero-mean Gaussian with std sigma_bar·√H).
- Directional expected gross edge per trade = (2·ACC - 1)·E|R_H|.
- Net edge = gross - round_trip_cost. Break-even ⇒ ACC* = 0.5 +
  round_trip_cost / (2·E|R_H|),  then  AUC* = Φ(√2·Φ⁻¹(ACC*)).

This is a conservative analytic CEILING, not a backtest: it assumes the move
magnitude is independent of whether the call was right, and ignores compounding,
position sizing, and serial structure. It is a kill-the-class sanity bound.

Stdlib-only (math); reuses the standard-normal helpers in ``normal_distribution``
(SoT — no second CDF implementation).
"""

from __future__ import annotations

import math

from src.shared.math.normal_distribution import (
    inverse_standard_normal_cdf,
    standard_normal_cdf,
)

_SQRT_TWO = math.sqrt(2.0)
#: E|Z| for Z ~ N(0,1) — the mean absolute value of a standard normal.
_MEAN_ABS_STD_NORMAL = math.sqrt(2.0 / math.pi)

#: Sentinel: a break-even AUC of 1.0 means "unachievable" — even a perfect
#: directional caller (AUC→1) cannot cover the cost over this holding period.
UNACHIEVABLE_BREAK_EVEN_AUC = 1.0


def round_trip_cost_fraction(taker_fee: float, slippage: float) -> float:
    """Round-trip cost as a fraction of notional: entry+exit fee plus entry+exit slippage."""
    if taker_fee < 0.0 or slippage < 0.0:
        raise ValueError(f"taker_fee and slippage must be non-negative, got {taker_fee}, {slippage}")
    return 2.0 * (taker_fee + slippage)


def auc_to_directional_accuracy(auc: float) -> float:
    """Balanced optimal-threshold accuracy implied by a binormal ROC-AUC.

    ACC = Φ(Φ⁻¹(AUC) / √2). AUC=0.5 → 0.5; strictly increasing on (0, 1).
    """
    if not 0.0 < auc < 1.0:
        raise ValueError(f"auc must be in (0, 1), got {auc}")
    return standard_normal_cdf(inverse_standard_normal_cdf(auc) / _SQRT_TWO)


def directional_accuracy_to_auc(accuracy: float) -> float:
    """Inverse of :func:`auc_to_directional_accuracy`: AUC = Φ(√2·Φ⁻¹(ACC))."""
    if not 0.0 < accuracy < 1.0:
        raise ValueError(f"accuracy must be in (0, 1), got {accuracy}")
    return standard_normal_cdf(_SQRT_TWO * inverse_standard_normal_cdf(accuracy))


def expected_absolute_move(sigma_bar: float, holding_bars: float) -> float:
    """E|R_H| over an H-bar hold: sigma_bar·√H·√(2/π) (mean abs of a Gaussian move)."""
    if sigma_bar < 0.0:
        raise ValueError(f"sigma_bar must be non-negative, got {sigma_bar}")
    if holding_bars <= 0.0:
        raise ValueError(f"holding_bars must be positive, got {holding_bars}")
    return sigma_bar * math.sqrt(holding_bars) * _MEAN_ABS_STD_NORMAL


def expected_net_edge_per_trade(
    *,
    auc: float,
    sigma_bar: float,
    holding_bars: float,
    round_trip_cost: float,
) -> float:
    """Expected net per-trade return: (2·ACC - 1)·E|R_H| - round_trip_cost."""
    accuracy = auc_to_directional_accuracy(auc)
    gross = (2.0 * accuracy - 1.0) * expected_absolute_move(sigma_bar, holding_bars)
    return gross - round_trip_cost


def break_even_auc(
    *,
    sigma_bar: float,
    holding_bars: float,
    round_trip_cost: float,
) -> float:
    """Minimum ROC-AUC a directional classifier needs to net break-even after cost.

    Returns 0.5 when cost is zero (any edge clears) and
    ``UNACHIEVABLE_BREAK_EVEN_AUC`` (1.0) when even a perfect directional caller
    cannot cover the cost over this hold (required accuracy ≥ 1).
    """
    if round_trip_cost < 0.0:
        raise ValueError(f"round_trip_cost must be non-negative, got {round_trip_cost}")
    move = expected_absolute_move(sigma_bar, holding_bars)
    if move <= 0.0:
        return UNACHIEVABLE_BREAK_EVEN_AUC
    accuracy_star = 0.5 + round_trip_cost / (2.0 * move)
    if accuracy_star >= 1.0:
        return UNACHIEVABLE_BREAK_EVEN_AUC
    return directional_accuracy_to_auc(accuracy_star)


__all__ = [
    "UNACHIEVABLE_BREAK_EVEN_AUC",
    "auc_to_directional_accuracy",
    "break_even_auc",
    "directional_accuracy_to_auc",
    "expected_absolute_move",
    "expected_net_edge_per_trade",
    "round_trip_cost_fraction",
]
