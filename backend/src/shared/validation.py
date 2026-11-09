"""
Shared validation helpers (Phase 2 §7.4 SoT).

Single place for symbol/timeframe validation so SignalRequest, backtest request
builders, and other entry points use the same rules. Consistency and security (injection).
"""

from src.shared.constants.timeframes import VALID_TIMEFRAMES_SIGNAL_AND_TRAINING


def validate_symbol_timeframe(symbol: str, timeframe: str) -> None:
    """
    Validate symbol and timeframe for signal/backtest entry points.

    Raises:
        ValueError: If symbol does not contain "/" (e.g. expected "BTC/USDT"),
            or if timeframe is not in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING.
    """
    if "/" not in symbol:
        raise ValueError(f"Invalid symbol format: {symbol!r}. Expected format: BTC/USDT")
    if timeframe not in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING:
        valid = sorted(VALID_TIMEFRAMES_SIGNAL_AND_TRAINING)
        raise ValueError(f"Invalid timeframe: {timeframe!r}. Valid: {valid}")
