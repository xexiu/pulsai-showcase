"""Kelly position sizing utilities."""

from __future__ import annotations

import math

MIN_SAMPLE_SIZE = 30
DEFAULT_MAX_POSITION_PCT = 0.05

# Half-Kelly edge for an even-money bet at full (100%) confidence: (1*1 - 0*1)/1 / 2 = 0.5.
# Used to normalize the confidence-derived edge to [0, 1] before scaling to the cap.
_MAX_EVEN_MONEY_HALF_KELLY_EDGE = 0.5


def discrete_kelly_fraction(*, win_rate: float, avg_win: float, avg_loss: float) -> float:
    """The full discrete Kelly fraction f* = (p * W - q * L) / W, with ``avg_win`` W and ``avg_loss`` L both positive
    (the engine's spelling (p * b - q) / b with b = W / L is the same number). The ONE formula: half_kelly here and the
    backtest engine's kelly sizing (position_sizers.kelly_notional_usd) both call it, each with its own policy around."""
    return (win_rate * avg_win - (1.0 - win_rate) * avg_loss) / avg_win


def half_kelly(
    *,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    evaluated_signals: int,
    max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
) -> float:
    """Compute the half-Kelly position size as a fraction of capital.

    Returns 0.0 when sample size is too small, inputs are non-positive,
    or the expected value is negative.  Result is clamped to [0, max_position_pct].
    """
    if evaluated_signals < MIN_SAMPLE_SIZE:
        return 0.0
    if avg_win <= 0 or avg_loss <= 0:
        return 0.0

    full_kelly = discrete_kelly_fraction(win_rate=max(0.0, min(1.0, win_rate)), avg_win=avg_win, avg_loss=avg_loss)
    half_value = full_kelly / 2
    bounded = min(max(half_value, 0.0), max_position_pct)

    return float(bounded)


def heuristic_suggested_position_fraction(confidence: object) -> float | None:
    """Confidence-derived position-size hint (API `suggested_position_pct` SoT).

    Scales the max-position cap (``DEFAULT_MAX_POSITION_PCT``) by the confidence's
    even-money half-Kelly edge, normalized to ``[0, 1]``: a coin-flip (50%) → 0,
    certainty (100%) → the full cap. This differentiates across the whole
    confidence range, so high-confidence signals get distinct sizes instead of all
    pinning to the cap (the prior ``clamp(confidence - 0.5, 0, cap)`` saturated at
    55%, rendering every confident signal as an identical 5%).

    Confidence-only with symmetric (even-money) payoff assumptions; illustrative,
    not personal advice, not based on account or trade history. Returns ``None``
    when confidence is not a real numeric type or is not finite.
    """
    c = float(confidence) if isinstance(confidence, (int, float)) else math.nan
    if not math.isfinite(c):  # not a number, or not a finite one: no hint
        return None
    clamped = max(0.0, min(1.0, c))
    # Reuse the half-Kelly primitive, then normalize its even-money edge to [0, 1]
    # (max edge is _MAX_EVEN_MONEY_HALF_KELLY_EDGE at full confidence) before
    # scaling to the position cap. max_position_pct here only lifts the internal
    # clamp so we recover the raw edge.
    raw_half_edge = half_kelly(
        win_rate=clamped,
        avg_win=1.0,
        avg_loss=1.0,
        evaluated_signals=MIN_SAMPLE_SIZE,
        max_position_pct=_MAX_EVEN_MONEY_HALF_KELLY_EDGE,
    )
    normalized_edge = raw_half_edge / _MAX_EVEN_MONEY_HALF_KELLY_EDGE
    return float(normalized_edge * DEFAULT_MAX_POSITION_PCT)
