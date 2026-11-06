"""
Sprint 2.11: Quant-Grade Evaluation Metrics.

Adds institutional-quality metrics beyond basic Sharpe/Win Rate:
1. Sortino ratio — penalizes only downside deviation
2. IC (Information Coefficient) — Spearman correlation of predictions vs returns
3. Rank IC — Pearson correlation of ranks (robust to outliers)
4. Benchmark alpha — strategy return minus buy-and-hold return

WHY these metrics (per .cursorrules research-first mindset):
- Sharpe penalizes upside volatility, which is WRONG for crypto (huge up moves are good)
- IC/Rank IC are the gold standard at quant firms (Two Sigma, AQR, Citadel)
- Benchmark alpha answers: "Would I be better off just buying and holding BTC?"
- Together they measure: signal quality (IC), risk-adjusted return (Sortino), value-add (alpha)

PERFORMANCE: All computations are O(n) or O(n log n) — adds <1ms to backtest.

@see backtester_metrics.py — existing metrics (Sharpe, max drawdown, etc.)
@see backtester_types.py — BacktestResult schema
@see docs/01-business/ROADMAP.md — Sprint 2.11
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from src.shared.constants.position_sizing import MIN_BARS_FOR_BETA_REGRESSION
from src.shared.math.zero_dispersion import is_near_zero_std, is_near_zero_variance


def calculate_sortino_ratio(
    net_returns: np.ndarray,
    risk_free_rate: float = 0.0,
    annualization_factor: float = 1.0,
) -> float:
    """
    Calculate the Sortino ratio (downside-risk-adjusted return).

    Sortino = (mean_return - risk_free) / downside_deviation * annualization_factor

    WHY Sortino > Sharpe for crypto:
    - Sharpe: std(ALL returns) — penalizes +50% days as "risky"
    - Sortino: std(NEGATIVE returns only) — only penalizes losses
    - BTC can have 10% up-days — those shouldn't count as risk

    Args:
        net_returns: Array of per-trade net returns
        risk_free_rate: Risk-free rate per period (default 0.0)
        annualization_factor: Scaling factor (e.g., sqrt(252) for daily)

    Returns:
        Sortino ratio (capped at 999.0 for consistency with profit_factor)
    """
    if len(net_returns) == 0:
        return 0.0

    excess_returns = net_returns - risk_free_rate
    mean_excess = float(np.mean(excess_returns))

    if mean_excess == 0.0 and np.all(net_returns == 0.0):
        return 0.0

    # Downside deviation: std of returns below the target (risk-free rate)
    # Only consider returns that are BELOW the target
    downside_returns = excess_returns[excess_returns < 0]

    # Downside deviation: RMS of negative excess returns
    # WHY RMS (not std): Downside deviation includes the zero-crossings
    # in the denominator to not overstate the ratio
    downside_dev = float(np.sqrt(np.mean(downside_returns**2))) if len(downside_returns) else 0.0

    if is_near_zero_std(downside_dev, mean_excess):
        # No losses (or only float-noise ones) → infinite Sortino, cap at 999.0
        return min(999.0, abs(mean_excess) * annualization_factor * 1000) if mean_excess > 0 else 0.0

    sortino = (mean_excess / downside_dev) * annualization_factor
    return float(min(sortino, 999.0))


def calculate_ic(
    predictions: np.ndarray,
    actual_returns: np.ndarray,
) -> float:
    """
    Calculate Information Coefficient (IC).

    IC = Spearman rank correlation between predicted probabilities and actual returns.

    WHY Spearman (not Pearson):
    - Spearman measures MONOTONIC relationship (rank-based)
    - Doesn't assume linear relationship between proba and returns
    - Robust to non-normal distributions (crypto returns are fat-tailed)

    Interpretation:
    - IC > 0.05: Decent signal (better than random)
    - IC > 0.1: Strong signal (rare, valuable)
    - IC < 0: Model is inversely predictive (flip signals!)

    Args:
        predictions: Model predicted probabilities (e.g., predict_proba[:, 1])
        actual_returns: Corresponding actual forward returns

    Returns:
        IC value in [-1, 1], or 0.0 if computation not possible
    """
    if len(predictions) == 0 or len(actual_returns) == 0:
        return 0.0

    if len(predictions) != len(actual_returns):
        return 0.0

    # If all predictions (or all returns) are identical, no ranking possible
    if is_near_zero_std(np.std(predictions), np.mean(predictions)) or is_near_zero_std(np.std(actual_returns), np.mean(actual_returns)):
        return 0.0

    # Spearman rank correlation
    corr, _ = stats.spearmanr(predictions, actual_returns)

    # Handle NaN from scipy (can happen with constant arrays)
    if isinstance(corr, float) and np.isnan(corr):
        return 0.0

    return float(corr) if isinstance(corr, float) else 0.0


def calculate_rank_ic(
    predictions: np.ndarray,
    actual_returns: np.ndarray,
) -> float:
    """
    Calculate Rank IC (Pearson correlation of ranks).

    Rank IC = Pearson(rank(predictions), rank(actual_returns))

    WHY Rank IC separately from IC:
    - IC uses scipy.stats.spearmanr (which IS rank-based under the hood)
    - Rank IC is the explicit "convert to ranks first, then Pearson"
    - They're mathematically equivalent, but Rank IC is more interpretable
    - Some quant shops track both for consistency checks

    Outlier robustness: A 100x return gets rank 1 (same as a 5% return
    that's the highest). The magnitude doesn't matter, only the ordering.

    Args:
        predictions: Model predicted probabilities
        actual_returns: Actual forward returns

    Returns:
        Rank IC in [-1, 1], or 0.0 if computation not possible
    """
    if len(predictions) == 0 or len(actual_returns) == 0:
        return 0.0

    if len(predictions) != len(actual_returns):
        return 0.0

    if is_near_zero_std(np.std(predictions), np.mean(predictions)) or is_near_zero_std(np.std(actual_returns), np.mean(actual_returns)):
        return 0.0

    # Convert to ranks
    pred_ranks = stats.rankdata(predictions)
    return_ranks = stats.rankdata(actual_returns)

    # Pearson correlation of ranks
    corr, _ = stats.pearsonr(pred_ranks, return_ranks)

    if isinstance(corr, float) and np.isnan(corr):
        return 0.0

    return float(corr) if isinstance(corr, float) else 0.0


def ols_intercept_beta(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[float, float]:
    """
    OLS with intercept: y ≈ alpha + beta * x.

    Returns:
        (alpha, beta). On degenerate inputs returns (0.0, 0.0).
    """
    if len(x) != len(y) or len(x) < MIN_BARS_FOR_BETA_REGRESSION:
        return (0.0, 0.0)
    xv = np.asarray(x, dtype=np.float64)
    yv = np.asarray(y, dtype=np.float64)
    if not np.all(np.isfinite(xv)) or not np.all(np.isfinite(yv)):
        return (0.0, 0.0)
    vx = float(np.var(xv))
    mx = float(np.mean(xv))
    my = float(np.mean(yv))
    if is_near_zero_variance(vx, mx):
        return (my, 0.0)
    beta = float(np.mean((xv - mx) * (yv - my)) / vx)
    alpha = my - beta * mx
    return (alpha, beta)


def trade_aligned_benchmark_returns(
    trades: list[Any],  # Trade; avoid circular import typing at runtime
    close_prices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build per-trade benchmark holding return vs strategy net return for regression.

    Benchmark move uses entry/exit **close** indices (same convention as chart window).
    Short trades use inverted benchmark move so long/short both express PnL vs spot path.
    """
    xs: list[float] = []
    ys: list[float] = []
    for t in trades:
        en = getattr(t, "entry_candle_index", None)
        ex = getattr(t, "exit_candle_index", None)
        if en is None or ex is None:
            continue
        if ex <= en or ex >= len(close_prices) or en < 0:
            continue
        c_en = float(close_prices[en])
        c_ex = float(close_prices[ex])
        if c_en <= 0:
            continue
        direction = int(getattr(t, "direction", 1))
        bench = direction * (c_ex - c_en) / c_en
        xs.append(bench)
        ys.append(float(getattr(t, "net_return", 0.0)))
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def calculate_benchmark_alpha(
    strategy_return: float,
    benchmark_return: float,
) -> float:
    """
    Calculate alpha (excess return vs benchmark).

    Alpha = strategy_return - benchmark_return

    WHY alpha:
    - A +10% strategy return is meaningless if BTC did +50%
    - Alpha measures the VALUE ADDED by the strategy
    - Negative alpha = you'd be better off just buying and holding

    Args:
        strategy_return: Capital total return of the trading strategy
            (``sum(net_pnl) / starting_balance``), same unit as buy-and-hold.
            Do NOT pass ``sum(per-trade notional %)`` — leverage makes that
            incomparable to first→last close B&H and falsely understates alpha.
        benchmark_return: Total return of buy-and-hold benchmark

    Returns:
        Alpha (positive = outperformance, negative = underperformance)
    """
    return strategy_return - benchmark_return


def calculate_quant_metrics(
    net_returns: np.ndarray,
    predictions: np.ndarray | None,
    actual_returns: np.ndarray | None,
    benchmark_return: float,
    annualization_factor: float = 1.0,
    risk_free_rate: float = 0.0,
    *,
    strategy_capital_return: float,
) -> dict[str, float]:
    """
    Calculate all quant-grade metrics in a single call.

    WHY a bundle function:
    - Backtester calls ONE function, gets all new metrics
    - Returns a typed dict, ready to merge into BacktestResult
    - Handles None predictions gracefully (classic strategies have no ML proba)

    Args:
        net_returns: Per-trade net returns (notional %) — used for Sortino only
        predictions: Model predicted probabilities (None for classic strategies)
        actual_returns: Actual forward returns (None for classic strategies)
        benchmark_return: Buy-and-hold return for alpha calculation
        annualization_factor: For Sortino annualization
        risk_free_rate: Risk-free rate for Sortino
        strategy_capital_return: Capital total return for benchmark alpha
            (``sum(net_pnl) / starting_balance``). REQUIRED and keyword-only: the former
            ``None`` fallback to ``sum(net_returns)`` published a wrong alpha on a live
            public row, so there is no longer a way to omit it and get a number anyway.

    Returns:
        Dict with keys: sortino_ratio, information_coefficient, rank_ic, benchmark_alpha
    """
    sortino = calculate_sortino_ratio(
        net_returns,
        risk_free_rate=risk_free_rate,
        annualization_factor=annualization_factor,
    )

    # IC and Rank IC require predictions (ML models only)
    if predictions is not None and actual_returns is not None:
        ic = calculate_ic(predictions, actual_returns)
        rank_ic = calculate_rank_ic(predictions, actual_returns)
    else:
        ic = 0.0
        rank_ic = 0.0

    # NO FALLBACK. This used to default to `sum(net_returns)` when the capital return was
    # omitted -- the exact quantity `calculate_benchmark_alpha` forbids ("Do NOT pass sum(per-trade
    # notional %) ... falsely understates alpha") -- and then labelled the result `benchmark_alpha`.
    #
    # It shipped. MEASURED on prod 2026-09-15, PUBLIC row `f111ac10`: stored alpha -6.712 against
    # total_return 23.064 and B&H 14.400, whose difference is 8.664. Solving backwards, the value
    # passed was 7.688 -- the notional sum. A 15.4-point error that FLIPS THE SIGN: the row tells a
    # reader the book lost to buy-and-hold while its own two components say it beat it. The other
    # eight public rows are self-consistent.
    #
    # The one production caller has passed the capital return correctly since its own fix, so the
    # default was serving nobody and silently arming that defect for the next caller. Required and
    # keyword-only: omission is now a TypeError at the call site, not a wrong number in public.
    alpha = calculate_benchmark_alpha(float(strategy_capital_return), benchmark_return)

    return {
        "sortino_ratio": sortino,
        "information_coefficient": ic,
        "rank_ic": rank_ic,
        "benchmark_alpha": alpha,
    }
