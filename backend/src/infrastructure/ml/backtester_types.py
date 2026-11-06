"""
Backtester Types - Data structures for backtesting.

Contains:
- ExitStrategy enum
- ExchangeFees Pydantic model
- Trade Pydantic model
- BacktestResult Pydantic model

WHY PYDANTIC (refactored from dataclass):
- Type validation at runtime (catches bugs early)
- ConfigDict(from_attributes=True) for ORM compatibility
- Consistent with API schemas (TradeSchema, etc.)
- .model_dump() replaces .to_dict() boilerplate

@see backtester.py for main CryptoBacktester class
@see .cursorrules - "schema consistency" requirement
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import Exchange
from src.shared.constants.backtest_exit_types import BACKTEST_EXIT_TYPE_SIGNAL
from src.shared.constants.fees import (
    BINANCE_FUTURES_MAKER_FEE,
    BINANCE_FUTURES_TAKER_FEE,
    BINANCE_MAKER_FEE,
    BINANCE_TAKER_FEE,
    BITGET_FUTURES_MAKER_FEE,
    BITGET_FUTURES_TAKER_FEE,
    BITGET_MAKER_FEE,
    BITGET_TAKER_FEE,
    DEFAULT_SLIPPAGE,
)

__all__ = [
    "EXCHANGE_FEES",
    "EXIT_STRATEGY_SPECS",
    "PERP_EXCHANGE_FEES",
    "BacktestResult",
    "Exchange",
    "ExchangeFees",
    "ExitStrategy",
    "ExitStrategySpec",
    "Trade",
    "VisualizationTrade",
    "barrier_exit_strategy_values",
    "exit_strategy_spec",
    "grid_swept_strategies",
]


class ExitStrategy(Enum):
    """Exit strategy options for backtesting."""

    FIXED_HOLDING = "fixed_holding"  # Exit after N candles (MVP)
    RAW_SIGNAL = "raw_signal"  # Exit on opposite signal (3-class)
    FIXED_TPSL = "fixed_tpsl"  # Fixed % stop-loss/take-profit
    RISK_REWARD = "risk_reward"  # SL + R:R ratio for TP
    ATR_BASED = "atr_based"  # Volatility-adaptive SL/TP
    DYNAMIC_TPSL = "dynamic_tpsl"  # ATR-derived TP/SL with regime-aware dynamic constraints
    PREDICTED_REGRESSOR = "predicted_regressor"  # MFE/MAE regressor-priced TP/SL (D1b research)
    TRAILING_STOP = "trailing_stop"  # Trail profits, lock gains
    MIN_PROFIT_AFTER_FEES = "min_profit_after_fees"  # Exit only when fees covered + net PnL positive
    THIN_STOP_LADDER = "thin_stop_ladder"  # Book-set stop per signal + breakeven + TP parts + runner (5m research)


class AddExitPlan(Enum):
    """The exit plan a DCA add rides (SOL-ADD-ON-REPEAT, owner 2026-10-21)."""

    NEW_CALL = "new_call"  # the add's own call re-plans the whole position: its stop and targets from the add's fill
    FIRST_FILL = "first_fill"  # the first fill's stop and targets stay; only the size grows
    #: NEW_CALL while the new stop sits inside the averaged position's liquidation price, else the plan in force; an add
    #: whose stop would sit past liquidation either way is refused -- the stop always fills before liquidation.
    NEW_CALL_INSIDE_LIQUIDATION = "new_call_inside_liquidation"


#: The exits whose stop IS ``stop_loss_pct`` of the entry (compute_tpsl_levels prices them with compute_fixed_tpsl_levels):
#: the only stop a user request names before the trade, so the only one risk_sized sizing can read from a request.
PERCENT_STOP_EXITS: frozenset[ExitStrategy] = frozenset({ExitStrategy.FIXED_TPSL, ExitStrategy.RISK_REWARD})


@dataclass(frozen=True)
class ExitStrategySpec:
    """Behavioural classification of ONE exit strategy — the single source of truth every consumer
    derives from or is guard-validated against, so a new ``ExitStrategy`` can never silently drift out
    of sync with the code that dispatches, sweeps, or time-boxes it.

    Attributes:
        is_barrier: Places a TP/SL barrier — the ``holding_periods`` deadline is only a SAFETY VALVE
            (mirrors ``shared.constants.backtest_exit_deadlines.BARRIER_EXIT_STRATEGIES``, cross-checked
            by a guard test since the shared layer may not import this infrastructure module).
        is_grid_swept: Participates in the capital-backtest exit grid (``exit_grid.build_fifo_oos_exit_grid``);
            a guard test fails if a swept strategy has no grid coverage.
        handled_in_main_loop: Dispatched by ``CryptoBacktester`` itself (needs signals / regressor arrays),
            NOT by the shared ``backtester_exits.determine_exit`` — which fails loud on anything else.
        has_fixed_levels: ``compute_tpsl_levels`` returns concrete SL/TP prices (else ``(None, None)``).
        is_research_only: Needs per-signal inputs a user-facing backtest request cannot supply (the book's own
            stop column), so it is kept off the public exit options a user can pick.
    """

    is_barrier: bool
    is_grid_swept: bool
    handled_in_main_loop: bool
    has_fixed_levels: bool
    is_research_only: bool = False


#: SoT classification of every ExitStrategy. A completeness guard test asserts this dict covers the enum
#: exactly, so adding a strategy is a compile-time-visible, test-enforced act — never a silent omission.
EXIT_STRATEGY_SPECS: dict[ExitStrategy, ExitStrategySpec] = {
    ExitStrategy.FIXED_HOLDING: ExitStrategySpec(is_barrier=False, is_grid_swept=True, handled_in_main_loop=False, has_fixed_levels=False),
    ExitStrategy.RAW_SIGNAL: ExitStrategySpec(is_barrier=False, is_grid_swept=False, handled_in_main_loop=True, has_fixed_levels=False),
    ExitStrategy.FIXED_TPSL: ExitStrategySpec(is_barrier=True, is_grid_swept=True, handled_in_main_loop=False, has_fixed_levels=True),
    ExitStrategy.RISK_REWARD: ExitStrategySpec(is_barrier=True, is_grid_swept=True, handled_in_main_loop=False, has_fixed_levels=True),
    ExitStrategy.ATR_BASED: ExitStrategySpec(is_barrier=True, is_grid_swept=True, handled_in_main_loop=False, has_fixed_levels=True),
    ExitStrategy.DYNAMIC_TPSL: ExitStrategySpec(is_barrier=True, is_grid_swept=True, handled_in_main_loop=False, has_fixed_levels=True),
    ExitStrategy.PREDICTED_REGRESSOR: ExitStrategySpec(is_barrier=True, is_grid_swept=False, handled_in_main_loop=True, has_fixed_levels=True),
    ExitStrategy.TRAILING_STOP: ExitStrategySpec(is_barrier=True, is_grid_swept=True, handled_in_main_loop=False, has_fixed_levels=True),
    ExitStrategy.MIN_PROFIT_AFTER_FEES: ExitStrategySpec(is_barrier=True, is_grid_swept=True, handled_in_main_loop=False, has_fixed_levels=False),
    # Not in the canonical grid: it applies only to a book that carries its own stop column, so the hypothesis
    # grid adds it per book (exit_grid.build_hypothesis_exit_grid(thin_stop=True)).
    ExitStrategy.THIN_STOP_LADDER: ExitStrategySpec(
        is_barrier=True, is_grid_swept=False, handled_in_main_loop=True, has_fixed_levels=True, is_research_only=True
    ),
}


def exit_strategy_spec(exit_strategy: ExitStrategy) -> ExitStrategySpec:
    """Return the SoT spec for a strategy, failing loud if a new enum member has no spec (guard-tested)."""
    try:
        return EXIT_STRATEGY_SPECS[exit_strategy]
    except KeyError as exc:  # pragma: no cover - guarded by test_exit_strategy_specs completeness test
        msg = f"ExitStrategy {exit_strategy!r} has no EXIT_STRATEGY_SPECS entry — classify it (backtester_types.py)."
        raise KeyError(msg) from exc


def barrier_exit_strategy_values() -> frozenset[str]:
    """The ``.value``s of every barrier strategy, derived from the SoT specs (shared layer mirrors this)."""
    return frozenset(strategy.value for strategy, spec in EXIT_STRATEGY_SPECS.items() if spec.is_barrier)


def public_exit_strategies() -> tuple[ExitStrategy, ...]:
    """Strategies a user may pick in a backtest request -- every one not flagged ``is_research_only``."""
    return tuple(strategy for strategy, spec in EXIT_STRATEGY_SPECS.items() if not spec.is_research_only)


def public_exit_strategy(raw: str) -> ExitStrategy:
    """The exit a user request names, refused unless a user may pick it.

    The ONE parser for every user door (request schemas, ``run_backtester``, the backtest worker, the training
    validation backtest): a research-only exit needs the book's own per-signal columns, which no request carries.
    """
    public = public_exit_strategies()
    for strategy in public:
        if strategy.value == raw:
            return strategy
    valid = [strategy.value for strategy in public]
    msg = f"Invalid exit_strategy '{raw}'. Valid: {valid}"
    raise ValueError(msg)


def grid_swept_strategies() -> tuple[ExitStrategy, ...]:
    """Strategies the capital-backtest exit grid must cover (guard-tested against ``exit_grid``)."""
    return tuple(strategy for strategy, spec in EXIT_STRATEGY_SPECS.items() if spec.is_grid_swept)


class ExchangeFees(BaseModel):
    """
    Fee structure for an exchange (SPOT trading).

    Pydantic model for validated fee configuration.
    """

    model_config = ConfigDict(frozen=True)

    maker_fee: float  # Limit orders (cheaper)
    taker_fee: float  # Market orders (default)
    slippage: float  # Market impact


# SPOT fee configurations (2026 rates) - NO DISCOUNTS!
EXCHANGE_FEES: dict[Exchange, ExchangeFees] = {
    Exchange.BINANCE: ExchangeFees(
        maker_fee=BINANCE_MAKER_FEE,
        taker_fee=BINANCE_TAKER_FEE,
        slippage=DEFAULT_SLIPPAGE,
    ),
    Exchange.BITGET: ExchangeFees(
        maker_fee=BITGET_MAKER_FEE,
        taker_fee=BITGET_TAKER_FEE,
        slippage=DEFAULT_SLIPPAGE,
    ),
}

# PERPETUAL (USDⓈ-M / USDT-M) fee configurations — standard tier, NO DISCOUNTS.
#
# A leveraged lane is not a spot trade and is not priced like one. Until 2026-09-21 every
# `perp_*` lane in the capital cert paid the SPOT rate above (0.10% a leg), which is 2x the real
# futures taker and 5x the real futures maker — an overcharge on the side that kills books.
# Slippage is unchanged: the liquid majors this engine trades have the same market impact whether
# the instrument is spot or perp, and nothing measured says otherwise.
PERP_EXCHANGE_FEES: dict[Exchange, ExchangeFees] = {
    Exchange.BINANCE: ExchangeFees(
        maker_fee=BINANCE_FUTURES_MAKER_FEE,
        taker_fee=BINANCE_FUTURES_TAKER_FEE,
        slippage=DEFAULT_SLIPPAGE,
    ),
    Exchange.BITGET: ExchangeFees(
        maker_fee=BITGET_FUTURES_MAKER_FEE,
        taker_fee=BITGET_FUTURES_TAKER_FEE,
        slippage=DEFAULT_SLIPPAGE,
    ),
}


class Trade(BaseModel):
    """
    Represents a single trade with all costs.

    WHY Pydantic:
    - Validates field types at construction
    - Consistent with TradeSchema API contract
    - Properties preserved via @property decorator
    """

    model_config = ConfigDict(from_attributes=True)

    entry_price: float
    exit_price: float
    direction: int  # 1 = long, -1 = short
    size: float  # Position size in quote currency
    entry_fee: float
    exit_fee: float
    slippage_cost: float
    gross_pnl: float
    net_pnl: float
    #: Perp funding accrued over the hold (signed): <0 paid (long), >0 received (short).
    #: 0.0 for spot and whenever the funding overlay has not been applied.
    funding_pnl: float = 0.0
    entry_time: str | None = None
    exit_time: str | None = None
    #: How the position closed (realised outcome). SoT: ``backtest_exit_types``.
    exit_type: str = BACKTEST_EXIT_TYPE_SIGNAL
    #: Theoretical isolated liq touch price when ``exit_type`` is liquidation (chart overlay).
    theoretical_liquidation_price: float | None = None
    #: The price a resting stop closed the open parts at, when a stop closed the trade (thin-stop ladder); a ladder
    #: books the BLENDED price as ``exit_price``, so the fill is carried apart. None for any other exit.
    stop_fill: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    min_tp_price: float | None = None
    tp_1r_price: float | None = None
    full_tp_price: float | None = None
    dynamic_volatility_regime: str | None = None
    compound_fill_prices: list[float] | None = None
    compound_fill_entry_times: list[str] | None = None
    #: Bar indices into the OHLCV series (for benchmark beta / regression metrics).
    entry_candle_index: int | None = None
    exit_candle_index: int | None = None

    @property
    def gross_return(self) -> float:
        """Gross return before fees."""
        return self.gross_pnl / self.size if self.size > 0 else 0.0

    @property
    def net_return(self) -> float:
        """Net return after all costs."""
        return self.net_pnl / self.size if self.size > 0 else 0.0


class VisualizationTrade(TypedDict):
    """One trade as the chart hover reads it (``BacktestResult.get_trades_for_visualization``).

    An overlay price the trade never had is ABSENT, never None.
    """

    entry_time: str | None
    exit_time: str | None
    entry_price: float
    exit_price: float
    side: Literal["long", "short"]
    exit_type: str
    pnl: float
    pnl_pct: float
    entry_fee: float
    exit_fee: float
    net_pnl: float
    stop_loss_price: NotRequired[float]
    take_profit_price: NotRequired[float]
    min_tp_price: NotRequired[float]
    tp_1r_price: NotRequired[float]
    full_tp_price: NotRequired[float]
    dynamic_volatility_regime: NotRequired[str]


def _visualization_trade(t: Trade) -> VisualizationTrade:
    row: VisualizationTrade = {
        "entry_time": t.entry_time,
        "exit_time": t.exit_time,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "side": "long" if t.direction == 1 else "short",
        "exit_type": t.exit_type,
        "pnl": t.net_pnl,
        "pnl_pct": (t.net_pnl / t.size * 100) if t.size > 0 else 0,
        "entry_fee": t.entry_fee,
        "exit_fee": t.exit_fee,
        "net_pnl": t.net_pnl,
    }
    if t.stop_loss_price is not None:
        row["stop_loss_price"] = t.stop_loss_price
    if t.take_profit_price is not None:
        row["take_profit_price"] = t.take_profit_price
    if t.min_tp_price is not None:
        row["min_tp_price"] = t.min_tp_price
    if t.tp_1r_price is not None:
        row["tp_1r_price"] = t.tp_1r_price
    if t.full_tp_price is not None:
        row["full_tp_price"] = t.full_tp_price
    if t.dynamic_volatility_regime is not None:
        row["dynamic_volatility_regime"] = t.dynamic_volatility_regime
    return row


class BacktestResult(BaseModel):
    """
    Comprehensive backtest results with realistic metrics.

    WHY Pydantic:
    - Validates field types at construction
    - .model_dump() for serialization (replaces to_dict boilerplate)
    - Properties and methods preserved
    """

    model_config = ConfigDict(from_attributes=True)

    # Core metrics
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    #: WHICH measurement `max_drawdown` is: `"mark_to_market"` (the honest intrabar figure the
    #: money gate requires beside a leveraged number) or `"bar_close"` (closed-trade equity).
    #: The producer chooses conditionally on whether the caller opted into `leverage`, so the
    #: same column means two different things without this label. Optional with a safe default so
    #: every existing construction site keeps working unchanged.
    drawdown_basis: str = "bar_close"
    win_rate: float
    profit_factor: float

    # Balance tracking
    starting_balance: float
    final_balance: float
    net_pnl: float

    #: DID THE ACCOUNT SURVIVE. Absence is not an answer, which is the whole reason these exist.
    #:
    #: `exit_type_counts` simply omits a `liquidation` key when none occurred, so "survived" and
    #: "nobody measured" render identically — and the flattering reading wins by default. Four
    #: PUBLIC rows carry that shape today at 3x-6x with `max_open_positions = 1`: the figure
    #: travels and the fact does not. `detect_account_bankruptcy`'s own docstring records the
    #: cost: 892 corpus cells showed a full-wipe drawdown BESIDE a final above initial with
    #: `account_bankrupt: False`, one of them published at 3.69x B&H (SELECT/in-sample, never
    #: confirm-verified). Both numbers cannot be true; the drawdown is the one the price path
    #: backs.
    #:
    #: Defaulted for the same reason `drawdown_basis` is: every existing construction site keeps
    #: working unchanged. A default of False/0 is honest here ONLY because the producer now
    #: always computes them — see `calculate_metrics`.
    account_bankrupt: bool = False
    #: Trades whose `exit_type` was a liquidation. An explicit 0 says "measured, none happened".
    liquidation_exits: int = 0

    # Trade statistics
    num_trades: int
    num_wins: int
    num_losses: int
    avg_trade_return: float
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float

    # Cost breakdown
    total_fees: float
    total_slippage: float
    gross_return: float

    # Additional metrics
    calmar_ratio: float
    avg_trade_duration: float

    # Sprint 2.11: Quant-grade metrics
    # WHY optional (default 0.0): Backward compatibility with existing results
    # that were created before these metrics existed.
    sortino_ratio: float = 0.0
    information_coefficient: float = 0.0
    rank_ic: float = 0.0
    #: Capital excess vs B&H: ``total_return - benchmark_buy_hold_return`` (not sum of notional %).
    benchmark_alpha: float = 0.0
    #: Buy-and-hold total return over the same close window as ``benchmark_alpha`` (first→last close).
    benchmark_buy_hold_return: float = 0.0
    #: OLS beta of per-trade holding returns vs benchmark holding returns (0 when not computable).
    benchmark_beta: float = 0.0
    #: OLS intercept (per-trade return units); complements simple ``benchmark_alpha`` excess return.
    benchmark_alpha_regression: float = 0.0

    # Trade frequency metrics
    trades_per_day: float = 0.0
    high_frequency_warning: bool = False

    # Kelly sizing diagnostics (backtest only; default zeros keep JSON stable)
    kelly_effective_fraction_mean: float = 0.0
    kelly_effective_fraction_p50: float = 0.0
    kelly_effective_fraction_p95: float = 0.0
    kelly_regime_stratified_fallback_bars: int = 0
    per_regime_trade_counts: dict[str, int] = Field(default_factory=dict)
    #: Trade count by realised ``exit_type`` (take_profit / stop_loss / trailing_stop /
    #: min_profit / opposite_signal / liquidation / timeout / signal). A barrier strategy
    #: dominated by ``timeout`` never let its TP/SL trigger within the holding deadline.
    exit_type_counts: dict[str, int] = Field(default_factory=dict)

    trades: list[Trade] = Field(default_factory=list)

    def to_metrics_dict(self) -> dict[str, object]:
        """
        Convert to dictionary with metrics only (excludes trades).

        WHY exclude trades:
        - Trades can be thousands of items (large payload)
        - API responses need lightweight summary
        - Use get_trades_for_visualization() for limited trades

        Use model_dump() if you need everything including trades.

        Returns:
            Dict with all metrics, avg_trade_duration included, trades excluded.
        """
        return self.model_dump(exclude={"trades"})

    # Backward compatibility alias
    # TODO (2026-02): Remove after all callers migrated to to_metrics_dict()
    def to_dict(self) -> dict[str, object]:
        """Deprecated: Use to_metrics_dict() instead."""
        return self.to_metrics_dict()

    def get_trades_for_visualization(self, max_trades: int = 200) -> list[VisualizationTrade]:
        """
        Get trades formatted for frontend signal visualization.

        Includes entry_fee, exit_fee, net_pnl for hover text (per Chart DRY plan).
        """
        trades_to_export = self.trades[-max_trades:] if len(self.trades) > max_trades else self.trades
        return [_visualization_trade(t) for t in trades_to_export]

    @property
    def is_profitable(self) -> bool:
        """Check if strategy is profitable after costs."""
        return self.total_return > 0 and self.sharpe_ratio > 0

    def meets_threshold(self, min_sharpe: float = 1.0) -> bool:
        """Check if Sharpe ratio meets minimum threshold."""
        return self.sharpe_ratio >= min_sharpe
