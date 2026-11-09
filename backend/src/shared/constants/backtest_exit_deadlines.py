"""Backtest barrier-exit deadline policy + advisory (single source of truth).

WHY this module exists (the execution-vs-label decoupling):
``holding_periods`` is applied to EVERY exit strategy as a vertical (time) barrier. For
*barrier* strategies (TP/SL/ATR/trailing/min-profit) it is only a SAFETY VALVE -- the
barrier itself should decide the exit. The default of ``DEFAULT_HOLDING_PERIODS`` (4) is
the training LABEL horizon leaking into execution and is far too tight on fast
timeframes: the deadline force-closes most trades (``exit_type='timeout'``) before TP/SL
can trigger. This module is the SoT for (a) which strategies are barrier strategies and
(b) the per-timeframe deadline below which a barrier strategy is likely starved.

This is INTENTIONALLY separate from the training label horizon
(``TRAINING_TIMEFRAME_POLICIES`` / ``DEFAULT_HOLDING_PERIODS``): labelling and execution
are different concerns and must not share one default.
"""

from __future__ import annotations

from typing import Final

from src.shared.backtest_holding_periods_bounds import resolve_backtest_holding_periods_max

#: Exit strategies that place a TP/SL barrier -- the ``holding_periods`` deadline is only
#: a safety valve for these, NOT the primary exit. Mirrors ``ExitStrategy`` values;
#: ``fixed_holding`` and ``raw_signal`` are EXCLUDED (their holding/opposite-signal IS the
#: exit). Kept as strings to avoid a shared->infrastructure import; a test asserts this set
#: stays in sync with the ``ExitStrategy`` enum so a new strategy must be classified.
BARRIER_EXIT_STRATEGIES: Final[frozenset[str]] = frozenset(
    {
        "fixed_tpsl",
        "risk_reward",
        "atr_based",
        "dynamic_tpsl",
        "predicted_regressor",  # MFE/MAE-regressor-priced TP/SL barrier (deadline is only a safety valve)
        "trailing_stop",
        "min_profit_after_fees",
        "thin_stop_ladder",  # book-set stop + targets + runner; the deadline is the max-hold fallback
    }
)

#: Per-timeframe minimum deadline (candles) below which a barrier strategy is likely
#: force-closed by the clock before its TP/SL can trigger. Deliberately a conservative
#: FLOOR (not an optimum -- the optimum is a research question) and TF-aware: starvation
#: is worst on fast TFs (4 bars of 5m is ~20 min -- absurd for a 2% barrier) and harmless
#: on slow TFs (4 daily bars is days). Aligned with the FE holding-period guidance.
RECOMMENDED_BARRIER_MIN_DEADLINE_BY_TIMEFRAME: Final[dict[str, int]] = {
    # 1m (LTF since 2026-10-11): 5m's floor scaled by bars-per-day (24 x 5 = 120 bars), the same
    # 2-hour wall-clock floor; inside the owner's 240-bar (4 h) 1m max hold. Without this row the
    # cert's barrier timeout for a 1m book was the 8-bar default -- 8 minutes.
    "1m": 120,
    "5m": 24,
    "15m": 16,
    "30m": 12,
    "1h": 8,
    # 2h/6h interpolated into the existing ladder, which shortens in BARS as the bar lengthens
    # (1h 8 -> 4h 6 -> 12h 4): 2h sits just under 1h, 6h alongside its 4h/8h neighbours which
    # already share 6. A missing entry here is not a crash — the caller takes a default deadline —
    # so a 6h book would silently be given another timeframe's exit window.
    "2h": 7,
    "4h": 6,
    "6h": 6,
    "8h": 6,
    "12h": 4,
    "1d": 3,
    "3d": 2,
    "1w": 2,
}

#: Fallback floor for any timeframe missing from the table above.
DEFAULT_RECOMMENDED_BARRIER_MIN_DEADLINE: Final[int] = 8


def is_barrier_strategy(exit_strategy: str) -> bool:
    """True when the strategy relies on a TP/SL barrier (the deadline is only a safety valve)."""
    return exit_strategy in BARRIER_EXIT_STRATEGIES


def recommended_barrier_deadline(timeframe: str) -> int:
    """Recommended minimum ``holding_periods`` for a barrier strategy on this timeframe.

    Clamped to the per-timeframe maximum so the recommendation never exceeds what the
    backtest request schema accepts.
    """
    normalized = (timeframe or "").strip().lower()
    floor = RECOMMENDED_BARRIER_MIN_DEADLINE_BY_TIMEFRAME.get(
        normalized,
        DEFAULT_RECOMMENDED_BARRIER_MIN_DEADLINE,
    )
    return min(floor, resolve_backtest_holding_periods_max(normalized))


def _deadline_too_tight(timeframe: str, exit_strategy: str, holding_periods: int) -> bool:
    """A barrier strategy whose holding deadline is below the recommended minimum for its timeframe."""
    return is_barrier_strategy(exit_strategy) and holding_periods < recommended_barrier_deadline(timeframe)


def build_barrier_deadline_warning(
    timeframe: str,
    exit_strategy: str,
    holding_periods: int,
) -> str | None:
    """Advise when a barrier strategy's holding deadline is too tight to let TP/SL trigger.

    Returns a human-readable English warning (same convention as ``in_sample_warning``) or
    ``None`` when the strategy is not a barrier strategy or the deadline is adequate.
    """
    if not _deadline_too_tight(timeframe, exit_strategy, holding_periods):
        return None

    recommended = recommended_barrier_deadline(timeframe)
    return (
        f"Exit strategy '{exit_strategy}' on {timeframe} uses a TP/SL barrier, but "
        f"holding_periods={holding_periods} is below the recommended minimum of "
        f"{recommended} candles for this timeframe. Most trades may be force-closed at the "
        f"holding deadline before TP/SL can trigger (exit_type='timeout'); raise "
        f"holding_periods so the barrier -- not the clock -- decides the exit."
    )


__all__ = [
    "BARRIER_EXIT_STRATEGIES",
    "DEFAULT_RECOMMENDED_BARRIER_MIN_DEADLINE",
    "RECOMMENDED_BARRIER_MIN_DEADLINE_BY_TIMEFRAME",
    "build_barrier_deadline_warning",
    "is_barrier_strategy",
    "recommended_barrier_deadline",
]
