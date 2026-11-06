"""
Shared backtest defaults.

WHY this module exists:
- Backtest API, worker tasks, benchmark flows, and the backtester runtime all
  need the same default capital/position/fee behavior
- Duplicating literals like 10000.0 and 1 creates silent drift across paths
"""

from __future__ import annotations

from typing import Final

#: The two drawdown bases `calculate_metrics` can produce. Named constants because the value
#: travels into artifacts and is read back by the money gate; a bare string would drift between
#: writer and reader the way `liquidation_exits` null-vs-zero already has.
#:
#: Moved here from `infrastructure/ml/backtester_metrics.py` (2026-09-12): that file was over its
#: size baseline, and CODING_STANDARDS §12 puts values like these in a constants module anyway.
#: They are read by the metrics writer and by the test that pins which basis was recorded — two
#: sides of one contract, which is the case for a shared constant rather than a local literal.
DRAWDOWN_BASIS_BAR_CLOSE: Final[str] = "bar_close"
DRAWDOWN_BASIS_MARK_TO_MARKET: Final[str] = "mark_to_market"

#: A return needs two prices. Named so the guard in `calculate_metrics` reads as a contract.
MIN_CLOSE_PRICES_FOR_BENCHMARK: Final[int] = 2

DEFAULT_BACKTEST_INITIAL_CAPITAL = 10_000.0
BACKTEST_HOLDING_PERIODS_MIN = 1
BACKTEST_HOLDING_PERIODS_MAX = 100
BACKTEST_HOLDING_PERIODS_ABSOLUTE_CEILING = 1000
BACKTEST_MAX_HOLD_CALENDAR_DAYS = 14
#: Sub-hour timeframes, whose max hold is a calendar cap (candles/day x 14 days, ceiling 1000) rather
#: than the flat 100 candles. 1m joined 2026-10-11 with the LTF band: on the 100-candle cap a 1m book
#: could not even request the owner's 240-bar (4 h) hold, and the cert's hold sweep stopped at 60.
BACKTEST_HOLDING_PERIODS_INTRADAY_TIMEFRAMES: frozenset[str] = frozenset(
    {"1m", "5m", "15m", "30m"}  # GRID-SUBSET: sub-hour only by design; 1h/2h keep the 100-candle cap
)
DEFAULT_BACKTEST_MAX_OPEN_POSITIONS = 1
DEFAULT_BACKTEST_ATR_PERIOD = 14
DEFAULT_BACKTEST_ATR_MULTIPLIER = 2.0
DEFAULT_BACKTEST_MAX_SL_PCT = None
DEFAULT_BACKTEST_MIN_NET_PCT = 0.0
DEFAULT_BACKTEST_USE_TAKER_FEES = True
DEFAULT_VALIDATION_BACKTEST_MAX_OPEN_POSITIONS = 10
# Multi-model selection cap (Hub: avoid runaway when user selects many models)
MAX_MODEL_VERSIONS_SELECTION = 5
# ML-ML agreement window bounds (0-10, same range as hybrid_signal_neighborhood_candles)
ML_NEIGHBORHOOD_CANDLES_MAX = 10
# Strategy-validation gate (de Prado / Bailey). SoT for backtest_validation_statistics.
# Minimum trades for a credible P&L verdict — below this the margin of error on the
# win-rate/Sharpe is too wide to trust (López de Prado's institutional floor; a 27-trade
# backtest is statistical noise). Deflated-Sharpe confidence is the probability the true
# Sharpe beats the N-trial luck floor before a strategy is accepted.
BACKTEST_VALIDATION_MIN_TRADES = 200
# Research OOS gates (scout / TF-scaled research / certification). Scout ignores trade count;
# research scales min-trades with OOS bar count; certification keeps the institutional 200 floor.
RESEARCH_MIN_TRADES_FLOOR = 30
RESEARCH_OOS_BARS_PER_TRADE = 20
DEFAULT_DEFLATED_SHARPE_CONFIDENCE = 0.95
# Exploratory OOS tier (research scripts only — never model promotion). See ML_RESEARCH_STANDARDS §7.
EXPLORATORY_OOS_MIN_TRADES = 10
EXPLORATORY_OOS_MIN_DEFLATED_SHARPE = 0.80
# Probability-of-Backtest-Overfitting threshold: PBO > 0.5 means the in-sample-best
# config is, more often than not, below the out-of-sample median — i.e. selecting the
# best backtest is no better than a coin flip OOS. Above this, reject the search.
DEFAULT_PBO_OVERFIT_THRESHOLD = 0.5

# ── Model-quality composite score (post-training promotion gate) ──────────────
# The gate squashes each backtest metric to a bounded [0,1] term before the
# weighted sum, so the composite is comparable instead of an unbounded,
# Sharpe-dominated raw sum. The per-term logistic scales `k` are chosen so the
# realistic metric ranges land in the responsive middle of the curve (not the
# saturated tails): Sharpe ~[-1,3], profit-factor-1 ~[-1,2], Calmar ~[-2,5].
MODEL_QUALITY_SHARPE_SCALE = 2.0
MODEL_QUALITY_PROFIT_FACTOR_SCALE = 0.5
MODEL_QUALITY_CALMAR_SCALE = 1.0
# Composite term weights (sum to 1.0 so the bounded terms yield a bounded [0,1] score).
# Sharpe = primary risk-adjusted metric; win-rate = least informative alone.
MODEL_QUALITY_SHARPE_WEIGHT = 0.30
MODEL_QUALITY_PROFIT_FACTOR_WEIGHT = 0.25
MODEL_QUALITY_DRAWDOWN_WEIGHT = 0.20
MODEL_QUALITY_CALMAR_WEIGHT = 0.15
MODEL_QUALITY_WIN_RATE_WEIGHT = 0.10
# Relative-comparison tolerance on the bounded [0,1] score: a new model passes
# when its score >= production score - tolerance (a noise band, not a downgrade).
MODEL_QUALITY_COMPARISON_TOLERANCE = 0.02

# Promote-to-production soft gate: the minimum backtest profit_factor a candidate
# must have to promote without an explicit risk acknowledgement. 1.0 = break-even;
# below it the strategy is net-losing. SoT for
# src.application.services.model_quality_gate.evaluate_promotion_quality_gate.
MODEL_PROMOTE_MIN_PROFIT_FACTOR = 1.0

# Significance-gate fallbacks (used when post-training result_data lacks the value).
# DEFAULT_OPTUNA_TRIALS: legacy jobs persisted before n_trials was plumbed through.
# DEFAULT_TRIAL_SHARPE_STD_FALLBACK: the std of per-trial Sharpe across the Optuna
# search is NOT recoverable (the study stores best-so-far of a trading_performance
# objective, not raw per-trial Sharpe), so DSR deflation uses a conservative fixed
# dispersion assumption (Bailey & López de Prado). Real per-trial capture is deferred.
DEFAULT_OPTUNA_TRIALS = 100
DEFAULT_TRIAL_SHARPE_STD_FALLBACK = 0.4

# Arena daily backtest (refresh_arena_rankings) scoring window.
# WHY these exist: the window used to be a fixed 30 calendar days while the
# row gate was a fixed 100 bars. For any timeframe coarser than ~8h
# (30d*24h/100 = 7.2h/bar) a 30-day window can never hold 100 bars, so those
# models failed 'Insufficient OHLCV data' on every run regardless of data.
# The lookback is now derived from the required bar count per timeframe with a
# 30-day floor for intraday TFs (preserving the original recency intent).
ARENA_BACKTEST_MIN_ROWS = 100
"""Minimum raw OHLCV rows required before a model is backtested."""
ARENA_BACKTEST_MIN_WINDOW_DAYS = 30
"""Intraday floor: shortest lookback used regardless of timeframe."""
ARENA_BACKTEST_WARMUP_BARS = 200
"""Extra bars beyond MIN_ROWS to absorb indicator warmup (longest common
lookback ~200, e.g. a 200-period MA) so >= MIN_ROWS survive feature cleaning."""

# OOS research sweeps (hub POST /backtest/run): skip Redis response cache read/write.
# FE manual backtests omit this header and keep cache (repeat clicks, 24h historical TTL).
BACKTEST_RESEARCH_SWEEP_HEADER: str = "X-PulsAI-Research-Sweep"
BACKTEST_RESEARCH_SWEEP_HEADER_VALUE: str = "1"

# Risk/reward ratio used when constructing dynamic TP from a fixed SL distance.
# WHY 2.0: standard 1:2 R:R floor assumed by the dynamic SL/TP module when no
# explicit ratio is supplied by the caller.
DEFAULT_BACKTEST_RISK_REWARD_RATIO: float = 2.0

# Trailing-stop defaults (percent). WHY here: these were hardcoded as raw literals
# (trail_pct=0.5, trail_activation_pct=1.0) across CryptoBacktester, run_backtest, the training
# pipeline, the API schema, and the FE — with NO shared constant. Centralized so the
# exit-strategy registry + every consumer reference one SoT (kills silent drift).
DEFAULT_BACKTEST_TRAIL_PCT: float = 0.5
DEFAULT_BACKTEST_TRAIL_ACTIVATION_PCT: float = 1.0

#: The ONE pre-registered risk per trade the door's money grade sizes a book at (risk_sized_book): the owner's own
#: example, 2026-10-04 -- "$20 capital, only $2 risk". ALL-IN is graded separately and disclosed beside it, never
#: instead of it. The stop/target geometry it is applied to lives in domain/services/structure_stop_targets.
RISK_PER_TRADE_FRACTION: float = 0.10

__all__ = [
    "ARENA_BACKTEST_MIN_ROWS",
    "ARENA_BACKTEST_MIN_WINDOW_DAYS",
    "ARENA_BACKTEST_WARMUP_BARS",
    "BACKTEST_HOLDING_PERIODS_ABSOLUTE_CEILING",
    "BACKTEST_HOLDING_PERIODS_INTRADAY_TIMEFRAMES",
    "BACKTEST_HOLDING_PERIODS_MAX",
    "BACKTEST_HOLDING_PERIODS_MIN",
    "BACKTEST_MAX_HOLD_CALENDAR_DAYS",
    "BACKTEST_RESEARCH_SWEEP_HEADER",
    "BACKTEST_RESEARCH_SWEEP_HEADER_VALUE",
    "BACKTEST_VALIDATION_MIN_TRADES",
    "DEFAULT_BACKTEST_ATR_MULTIPLIER",
    "DEFAULT_BACKTEST_ATR_PERIOD",
    "DEFAULT_BACKTEST_INITIAL_CAPITAL",
    "DEFAULT_BACKTEST_MAX_OPEN_POSITIONS",
    "DEFAULT_BACKTEST_MAX_SL_PCT",
    "DEFAULT_BACKTEST_MIN_NET_PCT",
    "DEFAULT_BACKTEST_RISK_REWARD_RATIO",
    "DEFAULT_BACKTEST_TRAIL_ACTIVATION_PCT",
    "DEFAULT_BACKTEST_TRAIL_PCT",
    "DEFAULT_BACKTEST_USE_TAKER_FEES",
    "DEFAULT_DEFLATED_SHARPE_CONFIDENCE",
    "DEFAULT_OPTUNA_TRIALS",
    "DEFAULT_PBO_OVERFIT_THRESHOLD",
    "DEFAULT_TRIAL_SHARPE_STD_FALLBACK",
    "DEFAULT_VALIDATION_BACKTEST_MAX_OPEN_POSITIONS",
    "EXPLORATORY_OOS_MIN_DEFLATED_SHARPE",
    "EXPLORATORY_OOS_MIN_TRADES",
    "MAX_MODEL_VERSIONS_SELECTION",
    "ML_NEIGHBORHOOD_CANDLES_MAX",
    "MODEL_PROMOTE_MIN_PROFIT_FACTOR",
    "MODEL_QUALITY_CALMAR_SCALE",
    "MODEL_QUALITY_CALMAR_WEIGHT",
    "MODEL_QUALITY_COMPARISON_TOLERANCE",
    "MODEL_QUALITY_DRAWDOWN_WEIGHT",
    "MODEL_QUALITY_PROFIT_FACTOR_SCALE",
    "MODEL_QUALITY_PROFIT_FACTOR_WEIGHT",
    "MODEL_QUALITY_SHARPE_SCALE",
    "MODEL_QUALITY_SHARPE_WEIGHT",
    "MODEL_QUALITY_WIN_RATE_WEIGHT",
    "RESEARCH_MIN_TRADES_FLOOR",
    "RESEARCH_OOS_BARS_PER_TRADE",
    "RISK_PER_TRADE_FRACTION",
]
