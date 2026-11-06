"""
Backtester Metrics - Performance metrics calculation.

Calculates:
- Sharpe ratio (annualized)
- Max drawdown
- Win/loss statistics
- Profit factor
- Trade frequency metrics
- Sprint 2.11: Sortino ratio, IC, Rank IC, Benchmark Alpha (via quant_metrics.py)

WHY quant metrics are wired HERE (not in backtester.py):
- calculate_metrics() is the SINGLE place that builds BacktestResult
- All callers (backtester, walk-forward validator, compare endpoint) get quant metrics for free
- Keeps backtester.py focused on trade generation, not metric computation

@see backtester.py for main CryptoBacktester class
@see quant_metrics.py for quant-grade metric implementations
"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np

from src.domain.services.edge_lifecycle.capital_cert_bankruptcy import detect_account_bankruptcy
from src.infrastructure.ml.backtester_drawdown import (
    mark_to_market_max_drawdown,
    mark_to_market_unavailable_reason,
)
from src.infrastructure.ml.backtester_types import BacktestResult, Trade
from src.infrastructure.ml.quant_metrics import (
    calculate_quant_metrics,
    ols_intercept_beta,
    trade_aligned_benchmark_returns,
)
from src.shared.constants.backtest import (
    DRAWDOWN_BASIS_BAR_CLOSE,
    DRAWDOWN_BASIS_MARK_TO_MARKET,
    MIN_CLOSE_PRICES_FOR_BENCHMARK,
)
from src.shared.constants.backtest_leverage import BACKTEST_EXIT_TYPE_LIQUIDATION
from src.shared.constants.backtest_timeframe import (
    BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME,
    BACKTEST_HIGH_FREQUENCY_TRADES_PER_DAY_THRESHOLD,
    DEFAULT_BACKTEST_CANDLES_PER_DAY,
    DEFAULT_BACKTEST_HIGH_FREQ_THRESHOLD,
)
from src.shared.math.zero_dispersion import is_near_zero_std

logger = logging.getLogger(__name__)

## CONSIDERED AND REJECTED 2026-09-14: refusing the bar_close fallback at leverage.
##
## The idea was that at leverage a closed-trade drawdown is not coarser, it is false about ruin,
## so a levered run unable to compute MTM should raise instead of reporting one. It was built,
## and `TestARuinedAccountSaysSo::test_metrics_disclose_bankruptcy_and_liquidation_count` failed
## immediately -- that test drives a WIPED account at 5x with no intrabar data and asserts the
## result still DISCLOSES bankruptcy. It does, and it does not need MTM to: `detect_account_ruin`
## below reaches the same verdict from `final_balance <= 0.0`.
##
## So the refusal would have turned a correctly-disclosed ruin into a 500. The ruin signal is
## already independent of the drawdown basis, the basis is already stamped on every result, and
## the publish driver already refuses a `bar_close` row. Three mechanisms cover it; a fourth that
## breaks a working one is not a gate, it is a regression. The test had the better logic.


def calculate_metrics(
    trades: list[Trade],
    total_fees: float,
    total_slippage: float,
    position_size: float,
    holding_periods: int,
    timeframe: str,
    annualization_factor: float,
    num_candles: int = 0,
    initial_capital: float | None = None,
    close_prices: np.ndarray | None = None,
    low_prices: np.ndarray | None = None,
    high_prices: np.ndarray | None = None,
    predictions_proba: np.ndarray | None = None,
    actual_returns: np.ndarray | None = None,
    leverage: float | None = None,
) -> BacktestResult:
    """
    Calculate comprehensive metrics from trades.

    Includes both classic metrics (Sharpe, drawdown, win rate) and
    Sprint 2.11 quant-grade metrics (Sortino, IC, Rank IC, Benchmark Alpha).

    Args:
        trades: List of Trade objects
        total_fees: Total fees paid
        total_slippage: Total slippage cost
        position_size: Position size per trade
        holding_periods: Holding period in candles
        timeframe: Candle timeframe (1h, 4h, etc.)
        annualization_factor: Factor for annualizing Sharpe and Sortino
        num_candles: Number of candles in backtest
        initial_capital: Starting capital (defaults to position_size for backward compat)
        close_prices: Close price array for benchmark alpha calculation.
            None = alpha defaults to 0.0 (backward compatible).
            WHY optional: Classic signal backtests don't have close prices in this function.
        predictions_proba: Model predicted probabilities for IC/Rank IC.
            None = IC/Rank IC default to 0.0 (classic strategies have no ML probabilities).
            WHY optional: Probability pipeline threading is deferred — callers can
            explicitly pass probabilities when available.
        actual_returns: Actual forward returns corresponding to predictions_proba.
            Required alongside predictions_proba for IC/Rank IC computation.

    Returns:
        BacktestResult with all metrics including quant-grade (Sprint 2.11)
    """
    net_returns = np.array([t.net_return for t in trades])
    net_pnls = np.array([t.net_pnl for t in trades])
    gross_pnls = np.array([t.gross_pnl for t in trades])

    # Balance tracking (simple summation - consistent with fixed position sizing)
    # NOTE: This backtester uses FIXED POSITION SIZING (same capital per trade, no reinvestment)
    # Therefore, we use simple summation, not compound returns
    # This ensures: final_balance == equity_curve[-1] == starting + sum(net_pnl)
    #
    # WHY initial_capital:
    # - In realistic mode, starting_balance = initial_capital (e.g., $10,000)
    # - In legacy mode, starting_balance = position_size (backward compat)
    starting_balance = initial_capital if initial_capital is not None else position_size
    total_net_pnl = float(np.sum(net_pnls))
    total_gross_pnl = float(np.sum(gross_pnls))
    # Bankruptcy floor: a real account cannot go below $0 — the loop-level stop halts
    # trading at ruin, this keeps the reported balance/return physically possible even
    # if the ruining trade's fixed notional overshoots zero.
    final_balance = max(starting_balance + total_net_pnl, 0.0)

    # Total return (simple, consistent with fixed position sizing and equity curve),
    # floored at -100% (can't lose more than the whole account).
    total_return = total_net_pnl / starting_balance if starting_balance > 0 else 0.0
    total_return = max(total_return, -1.0)
    gross_return = total_gross_pnl / starting_balance if starting_balance > 0 else 0.0

    # Sharpe ratio (annualized, NET returns)
    # Guard against DEGENERATE dispersion: when every trade exits at the same stop, np.std of the
    # returns is float noise (measured 4.6e-17), not exactly 0, so a bare ``std > 0`` guard lets
    # ``avg / std`` overflow (observed Sharpe ~-2.6e15). The shared zero-dispersion guard floors it.
    avg_return = float(np.mean(net_returns))
    std_return = float(np.std(net_returns))
    sharpe_ratio = 0.0 if is_near_zero_std(std_return, avg_return) else (avg_return / std_return) * annualization_factor

    # Max drawdown (using cumulative balance, not compound returns)
    cumulative_balance = starting_balance + np.cumsum(net_pnls)
    running_max = np.maximum.accumulate(cumulative_balance)
    # Guard against division by zero (if running_max is 0)
    drawdown = np.where(running_max > 0, (cumulative_balance - running_max) / running_max, 0.0)
    # Floor at -100%: a real account cannot lose more than its capital. A drawdown
    # worse than -1.0 is a fixed-notional accounting artifact (trades booked "through
    # ruin"); the loop-level bankruptcy stop prevents most of it, this is the guard.
    max_drawdown = max(float(np.min(drawdown)), -1.0) if len(drawdown) > 0 else 0.0
    # HONEST drawdown at leverage (owner 2026-07-25 "fix and revalue"): prefer the bar-by-bar
    # mark-to-market DD when close prices + trade candle indices are available. The closed-trade DD
    # above only marks equity at exits, so a leveraged position underwater mid-hold but exiting flat
    # looks risk-free; the MTM path does not. Falls back to closed-trade DD when close prices absent.
    # `leverage` stays None for every caller that has not opted in, so the drawdown is byte-identical
    # to before. A caller that knows its lane multiple (perp_5x -> 5) passes it and gets the honest
    # isolated-margin cap instead of an unbounded mark. See mark_to_market_max_drawdown.
    mtm_drawdown = mark_to_market_max_drawdown(trades, low_prices, high_prices, starting_balance, leverage=leverage)
    # WHICH basis produced the number, recorded rather than left to be assumed.
    #
    # The choice above is CONDITIONAL — it depends on whether this caller opted into `leverage`
    # and supplied prices — so `max_drawdown` means two different measurements depending on who
    # called, and `ml-gate-leverage-capital-cert.md` requires the honest MTM drawdown beside any
    # leveraged number. A column that silently means two things is worse than a missing one.
    #
    # THE GAP THIS CLOSED IS CLOSED — re-measured 2026-09-10 over 3,478 artifacts:
    #   `drawdown_basis` occurrences   2026-08-22: 0 of 64 cert files
    #                                  2026-09-10: 1,018,021 (929,315 MTM / 88,706 bar_close)
    # so every MTM claim in the corpus is now verifiable from its own artifact. The stamp works;
    # this note records that rather than leaving the reader with the pre-fix number, which read as
    # a live defect and cost a wrong premise on 2026-09-10 (the corpus was judged unverifiable
    # from this comment alone, twenty minutes before the count was actually run).
    drawdown_basis = DRAWDOWN_BASIS_BAR_CLOSE
    if mtm_drawdown is not None:
        max_drawdown = mtm_drawdown
        drawdown_basis = DRAWDOWN_BASIS_MARK_TO_MARKET
    else:
        # SAY WHY, because falling back silently is how an understated drawdown gets published.
        # The bar_close branch is legitimate for classic-signal backtests with no intrabar data,
        # and indistinguishable from a leveraged run whose honest drawdown was simply unavailable.
        # Measured 2026-09-13: prod and localhost both stamped bar_close on the same 90-trade
        # leveraged config with identical numbers, and nothing in either process said which of the
        # five preconditions had failed. WARNING, not DEBUG: on a leveraged book this decides
        # whether the published number is the honest one.
        logger.warning(
            "mark-to-market drawdown unavailable (%s); reporting the closed-trade drawdown and stamping drawdown_basis=%s",
            mark_to_market_unavailable_reason(trades, low_prices, high_prices),
            DRAWDOWN_BASIS_BAR_CLOSE,
        )

    # Win/loss statistics
    wins = net_pnls[net_pnls > 0]
    losses = net_pnls[net_pnls < 0]
    num_wins = len(wins)
    num_losses = len(losses)
    win_rate = num_wins / len(trades) if len(trades) > 0 else 0.0

    # Profit factor
    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
    gross_loss = float(np.abs(np.sum(losses))) if len(losses) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0 if gross_profit > 0 else 0.0

    # Average/max win/loss
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
    max_win = float(np.max(wins)) if len(wins) > 0 else 0.0
    max_loss = float(np.min(losses)) if len(losses) > 0 else 0.0

    # Calmar ratio
    calmar_ratio = total_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

    # Trade frequency metrics
    cpd = BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME.get(timeframe, DEFAULT_BACKTEST_CANDLES_PER_DAY)
    days_in_backtest = num_candles / cpd if cpd > 0 else 1
    trades_per_day = len(trades) / days_in_backtest if days_in_backtest > 0 else 0.0

    threshold = BACKTEST_HIGH_FREQUENCY_TRADES_PER_DAY_THRESHOLD.get(timeframe, DEFAULT_BACKTEST_HIGH_FREQ_THRESHOLD)
    high_frequency_warning = trades_per_day > threshold

    # =========================================================================
    # Sprint 2.11: Quant-grade metrics (Sortino, IC, Rank IC, Benchmark Alpha)
    # =========================================================================
    #
    # WHY here and not in backtester.py:
    # - This function is the SINGLE builder of BacktestResult
    # - All callers (backtester, walk-forward, compare endpoint) benefit
    #
    # BENCHMARK ALPHA GUARD:
    # - When close_prices is None, we CANNOT compute a meaningful benchmark
    # - benchmark_return=0.0 would incorrectly set alpha=strategy_return
    # - So we explicitly force alpha=0.0 when close_prices is None
    has_close_prices = close_prices is not None and len(close_prices) >= MIN_CLOSE_PRICES_FOR_BENCHMARK

    benchmark_return = 0.0
    if has_close_prices and close_prices is not None:
        # WHY double check: mypy needs explicit `is not None` in this scope
        # for type narrowing (bool variable doesn't narrow)
        first_close = float(close_prices[0])
        last_close = float(close_prices[-1])
        if first_close > 0:
            benchmark_return = (last_close - first_close) / first_close

    # WHY strategy_capital_return=total_return (not sum(net_returns)):
    # Buy-and-hold is first→last close % on capital. Per-trade net_return is
    # notional %; with leverage, sum(notional %) << capital total_return and
    # falsely paints "underperformed B&H" while Total Return still beat B&H.
    quant = calculate_quant_metrics(
        net_returns=net_returns,
        predictions=predictions_proba,
        actual_returns=actual_returns,
        benchmark_return=benchmark_return,
        annualization_factor=annualization_factor,
        strategy_capital_return=total_return,
    )

    # Force alpha=0.0 when no close prices (can't compute benchmark)
    # Sortino is always valid (only needs net_returns from trades)
    # IC/Rank IC default to 0.0 when predictions_proba is None
    computed_alpha = quant["benchmark_alpha"] if has_close_prices else 0.0

    bench_buy_hold = benchmark_return if has_close_prices else 0.0
    bench_beta = 0.0
    bench_alpha_reg = 0.0
    if has_close_prices and close_prices is not None:
        bx, sy = trade_aligned_benchmark_returns(trades, close_prices)
        bench_alpha_reg, bench_beta = ols_intercept_beta(bx, sy)

    # Exit-type attribution: how each trade actually closed. A barrier strategy whose
    # trades are mostly ``timeout`` never let TP/SL trigger within the holding deadline --
    # surfacing this makes the starvation visible instead of hidden behind net metrics.
    exit_type_counts = dict(Counter(trade.exit_type for trade in trades))

    # DID THE ACCOUNT SURVIVE — asked here so the answer cannot be absent (C-0b).
    #
    # `exit_type_counts` omits a `liquidation` key when none occurred, so "survived" and "nobody
    # measured" render identically and the flattering reading wins. Reading the count OUT of that
    # dict rather than re-scanning `trades` keeps one source for how a trade closed.
    #
    # REUSE, not a second implementation: `detect_account_bankruptcy` is the SoT the CERT path
    # already uses to stamp `account_bankrupt` into every `capital_certification.json`. It takes
    # exactly what this function already holds, and it is fed `max_drawdown` only when that is the
    # honest MTM figure -- passing a bar-close drawdown would let its full-wipe branch fire on a
    # measurement that never saw the intrabar path, which is the opposite of its purpose.
    ruin = detect_account_bankruptcy(
        initial_capital=starting_balance,
        trades=trades,
        final_balance=final_balance,
        mark_to_market_drawdown=max_drawdown if drawdown_basis == "mark_to_market" else None,
    )

    return BacktestResult(
        account_bankrupt=ruin.account_bankrupt,
        liquidation_exits=int(exit_type_counts.get(BACKTEST_EXIT_TYPE_LIQUIDATION, 0)),
        total_return=total_return,
        sharpe_ratio=float(sharpe_ratio),
        max_drawdown=max_drawdown,
        drawdown_basis=drawdown_basis,
        win_rate=win_rate,
        profit_factor=min(profit_factor, 999.0),
        starting_balance=starting_balance,
        final_balance=final_balance,
        net_pnl=total_net_pnl,
        num_trades=len(trades),
        num_wins=num_wins,
        num_losses=num_losses,
        avg_trade_return=float(np.mean(net_returns)),
        avg_win=avg_win,
        avg_loss=avg_loss,
        max_win=max_win,
        max_loss=max_loss,
        total_fees=total_fees,
        total_slippage=total_slippage,
        gross_return=gross_return,
        calmar_ratio=calmar_ratio,
        avg_trade_duration=float(holding_periods),
        trades_per_day=trades_per_day,
        high_frequency_warning=high_frequency_warning,
        exit_type_counts=exit_type_counts,
        trades=trades,
        # Sprint 2.11: Quant-grade metrics
        sortino_ratio=quant["sortino_ratio"],
        information_coefficient=quant["information_coefficient"],
        rank_ic=quant["rank_ic"],
        benchmark_alpha=computed_alpha,
        benchmark_buy_hold_return=bench_buy_hold,
        benchmark_beta=bench_beta,
        benchmark_alpha_regression=bench_alpha_reg,
    )


def empty_result(initial_capital: float | None = None) -> BacktestResult:
    """
    Return empty result when no trades.

    WHY initial_capital:
    - User's capital does not vanish when an indicator produces 0 signals
    - starting_balance = final_balance = initial_capital (no trades = unchanged)
    - When None, use 0.0 for backward compatibility with legacy callers
    """
    capital = initial_capital if initial_capital is not None else 0.0

    return BacktestResult(
        total_return=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        profit_factor=0.0,
        starting_balance=capital,
        final_balance=capital,
        net_pnl=0.0,
        num_trades=0,
        num_wins=0,
        num_losses=0,
        avg_trade_return=0.0,
        avg_win=0.0,
        avg_loss=0.0,
        max_win=0.0,
        max_loss=0.0,
        total_fees=0.0,
        total_slippage=0.0,
        gross_return=0.0,
        calmar_ratio=0.0,
        avg_trade_duration=0.0,
        exit_type_counts={},
        trades=[],
    )
