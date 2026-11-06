"""Stateless trade-math helpers extracted from CryptoBacktester."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

import numpy as np
import polars as pl

from src.infrastructure.ml.backtester_exit_common import PlannedExit
from src.infrastructure.ml.backtester_raw_signal_exit import find_opposite_signal_exit
from src.infrastructure.ml.backtester_types import ExitStrategy, Trade
from src.shared.constants.backtest_leverage import (
    BACKTEST_EXIT_TYPE_LIQUIDATION,
    BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE,
)
from src.shared.math.linear_isolated_perp import (
    bankruptcy_price_linear_isolated,
    liquidation_price_linear_isolated_long,
    liquidation_price_linear_isolated_short,
)

logger = logging.getLogger(__name__)


def calculate_trade_pnl(
    entry_price: float,
    exit_price: float,
    direction: int,
    position_size: float,
    fee_rate: float,
    slippage_rate: float,
) -> tuple[float, float, float, float, float]:
    """
    Calculate trade P&L with fees and slippage.

    Returns:
        (gross_pnl, net_pnl, entry_fee, exit_fee, slippage_pnl)
    """
    entry_slippage = entry_price * slippage_rate * direction
    exit_slippage = exit_price * slippage_rate * (-direction)
    entry_fee = position_size * fee_rate
    exit_fee = position_size * fee_rate

    price_diff = exit_price - entry_price if direction == 1 else entry_price - exit_price
    gross_pnl = price_diff / entry_price * position_size

    slippage_cost = abs(entry_slippage) + abs(exit_slippage)
    slippage_pnl = slippage_cost / entry_price * position_size
    net_pnl = gross_pnl - entry_fee - exit_fee - slippage_pnl

    return gross_pnl, net_pnl, entry_fee, exit_fee, slippage_pnl


def to_iso_timestamp(ts: object) -> str | None:
    """Convert timestamp to ISO format string."""
    if ts is None:
        return None
    isoformat = getattr(ts, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    ts_str = str(ts)
    return ts_str.replace(" ", "T") if " " in ts_str and "T" not in ts_str else ts_str


def liquidation_trigger_price(entry_price: float, leverage: int, maintenance_margin_rate: float, direction: int) -> float:
    """The price at which a position entered at ``entry_price`` liquidates -- the line every liquidation scan reads."""
    if direction == 1:
        return liquidation_price_linear_isolated_long(entry_price, leverage, maintenance_margin_rate)
    return liquidation_price_linear_isolated_short(entry_price, leverage, maintenance_margin_rate)


def merge_planned_exit_with_intrabar_liquidation(
    fill_entry_candles: list[int],
    fill_prices: list[float],
    direction: int,
    leverage: int,
    maintenance_margin_rate: float,
    planned: tuple[int, float, str],
    low_np: np.ndarray,
    high_np: np.ndarray,
    *,
    exit_bar_fill: float | None = None,
) -> tuple[int, float, str, float | None]:
    """The planned exit, or a liquidation on the first bar the held position reached its liquidation price.

    Touch detection reads each bar's low (long) / high (short) against the liquidation price (ADR-013 §6); the fill is
    the BANKRUPTCY price, so a liquidated position loses exactly its margin (LIQ-ONE). ``exit_bar_fill``: where a
    resting stop closed the position on the planned exit bar -- that bar is read at the fill, not at its extreme.

    One position is one fill (``[entry_candle]``, ``[entry_price]``). A DCA / scaled-in position has more, and each
    scale-in moves the weighted-average entry and therefore the liquidation price: checking the whole span against the
    FINAL average under-detects a liquidation that fired on an earlier, closer average, which makes leveraged DCA look
    safer than it is. So each inter-fill segment is read against the liquidation price in force during it (the running
    average over the fills open so far). One scan for both: until 2026-10-18 the single-position door was a second
    definition delegating here with its own copy of the signature.

    Returns:
        (exit_candle, exit_fill_price, exit_type, the liquidation price when it fired, else None)
    """
    exit_candle, exit_price, exit_type = planned
    if leverage <= 0 or not fill_prices:
        return exit_candle, exit_price, exit_type, None
    end_all = min(exit_candle, len(low_np) - 1, len(high_np) - 1)
    adverse = low_np if direction == 1 else high_np
    n = len(fill_prices)
    for k in range(n):
        running_avg = float(sum(fill_prices[: k + 1]) / (k + 1))
        liq_px = liquidation_trigger_price(running_avg, leverage, maintenance_margin_rate, direction)
        seg_start = int(fill_entry_candles[k]) if k < len(fill_entry_candles) else exit_candle
        has_next_fill = k + 1 < n and k + 1 < len(fill_entry_candles)
        seg_end = (int(fill_entry_candles[k + 1]) - 1) if has_next_fill else end_all
        seg_end = min(seg_end, end_all)
        for j in range(max(seg_start, 0), seg_end + 1):
            held = exit_bar_fill if (j == exit_candle and exit_bar_fill is not None) else float(adverse[j])
            if (held <= liq_px) if direction == 1 else (held >= liq_px):
                return j, bankruptcy_price_linear_isolated(running_avg, leverage, direction), BACKTEST_EXIT_TYPE_LIQUIDATION, liq_px
    return exit_candle, exit_price, exit_type, None


def _planned_exit(
    signals: np.ndarray,
    open_prices: np.ndarray,
    df: pl.DataFrame,
    entry_candle: int,
    entry_price: float,
    direction: int,
    exit_strategy: ExitStrategy,
    holding_periods: int,
    determine_exit_fn: Callable[[int, float, int, pl.DataFrame, np.ndarray], PlannedExit | None],
) -> PlannedExit | None:
    """The trade's planned exit: RAW_SIGNAL reads the run's calls, every other strategy asks the engine's exit."""
    if exit_strategy != ExitStrategy.RAW_SIGNAL:
        return determine_exit_fn(entry_candle, entry_price, direction, df, open_prices)
    raw = find_opposite_signal_exit(entry_candle, signals, open_prices, direction, len(df), holding_periods)
    return None if raw is None else PlannedExit(*raw)


def create_and_record_trade(
    signal_candle: int,
    signal: int,
    signals: np.ndarray,
    df: pl.DataFrame,
    open_prices: np.ndarray,
    timestamps: Sequence[object],
    open_positions: list[tuple[int, float, float]],
    available_balance: float,
    *,
    exit_strategy: ExitStrategy,
    holding_periods: int,
    position_size: float,
    locked_collateral_usd: float,
    realistic_mode: bool,
    fee_rate: float,
    slippage_rate: float,
    determine_exit_fn: Callable[[int, float, int, pl.DataFrame, np.ndarray], PlannedExit | None],
    leverage: int = 0,
    maintenance_margin_rate: float = BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE,
    low_np: np.ndarray | None = None,
    high_np: np.ndarray | None = None,
) -> tuple[Trade, list[tuple[int, float, float]], float] | None:
    """
    Create and record a trade from signal.

    open_positions legs are (exit_candle, locked_collateral_usd, notional_usd).

    Returns (Trade, updated_open_positions, updated_available_balance) or None.
    """
    entry_candle = signal_candle + 1
    if entry_candle >= len(df):
        logger.debug("signal on bar %d has no fill bar inside the %d-bar frame -- no trade", signal_candle, len(df))
        return None
    entry_price = open_prices[entry_candle]
    direction = int(signal)

    planned = _planned_exit(signals, open_prices, df, entry_candle, entry_price, direction, exit_strategy, holding_periods, determine_exit_fn)
    if planned is None:
        return None

    exit_candle, exit_price, exit_type = planned.candle, planned.price, planned.exit_type
    theoretical_liquidation_price: float | None = None
    if leverage > 0 and low_np is not None and high_np is not None:
        exit_candle, exit_price, exit_type, theoretical_liquidation_price = merge_planned_exit_with_intrabar_liquidation(
            [entry_candle],
            [entry_price],
            direction,
            leverage,
            maintenance_margin_rate,
            (exit_candle, exit_price, exit_type),
            low_np,
            high_np,
            exit_bar_fill=planned.stop_fill,
        )

    updated_balance = available_balance
    if realistic_mode:
        updated_balance -= locked_collateral_usd

    updated_positions = [*open_positions, (exit_candle, locked_collateral_usd, position_size)]

    gross_pnl, net_pnl, entry_fee, exit_fee, slippage_cost = calculate_trade_pnl(
        entry_price,
        exit_price,
        direction,
        position_size,
        fee_rate,
        slippage_rate,
    )

    trade = Trade(
        entry_price=entry_price,
        exit_price=exit_price,
        direction=direction,
        size=position_size,
        entry_fee=entry_fee,
        exit_fee=exit_fee,
        slippage_cost=slippage_cost,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        entry_time=to_iso_timestamp(timestamps[entry_candle]),
        exit_time=(to_iso_timestamp(timestamps[exit_candle]) if exit_candle < len(timestamps) else None),
        exit_type=exit_type,
        theoretical_liquidation_price=theoretical_liquidation_price,
        stop_fill=None if exit_type == BACKTEST_EXIT_TYPE_LIQUIDATION else planned.stop_fill,  # a liquidation came first
        entry_candle_index=entry_candle,
        exit_candle_index=exit_candle,
    )
    return trade, updated_positions, updated_balance
