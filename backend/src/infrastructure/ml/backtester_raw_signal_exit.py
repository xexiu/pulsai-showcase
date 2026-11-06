"""RAW_SIGNAL exit-strategy helper extracted from CryptoBacktester."""

from __future__ import annotations

import numpy as np

from src.shared.constants.backtest_exit_types import (
    BACKTEST_EXIT_TYPE_OPPOSITE_SIGNAL,
    BACKTEST_EXIT_TYPE_TIMEOUT,
)


def find_opposite_signal_exit(
    entry_candle: int,
    signals: np.ndarray,
    open_prices: np.ndarray,
    direction: int,
    df_len: int,
    holding_periods: int,
) -> tuple[int, float, str] | None:
    """
    Find exit candle based on opposite signal (RAW_SIGNAL strategy).

    Scans forward from entry_candle for the next opposite signal:
    - LONG (direction=1): looks for SELL signal (== -1)
    - SHORT (direction=-1): looks for BUY signal (== 1)

    WHY scan from entry_candle (not entry_candle+1):
    - entry_candle is already i+1 (next candle after BUY signal)
    - A SELL signal AT entry_candle means the model flipped immediately

    Execution model: opposite signal at candle j -> position closed at j+1 open.
    Falls back to a ``timeout`` exit at the holding_periods deadline if no opposite
    signal is found (distinct from the opposite-signal close).

    Returns:
        (exit_candle, exit_price, exit_type) or None if no valid exit
    """
    opposite_signal = -direction
    max_scan = entry_candle + holding_periods

    for j in range(entry_candle, min(max_scan, len(signals))):
        if signals[j] == opposite_signal:
            exit_candle = j + 1
            if exit_candle >= df_len:
                return None
            return (exit_candle, open_prices[exit_candle], BACKTEST_EXIT_TYPE_OPPOSITE_SIGNAL)

    # No opposite signal within holding_periods -> timeout fallback
    fallback_candle = entry_candle + holding_periods
    if fallback_candle >= df_len:
        return None
    return (fallback_candle, open_prices[fallback_candle], BACKTEST_EXIT_TYPE_TIMEOUT)
