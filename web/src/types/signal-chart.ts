/**
 * Canonical Signal Chart Data Contract (Chart DRY Plan)
 *
 * Single source of truth for chart data shape used by:
 * - backtest/page (run result)
 * - backtest/[id] (DB backtest)
 * - SignalChartSection (signal_chart.json from training/model)
 *
 * WHY CANONICAL?
 * - All 3 consumers pass same shape to BacktestChart
 * - normalizeToChartData() maps each source to this contract
 * - Eliminates drift between pages (e.g. backtest/[id] missing EXIT/predictions)
 *
 * @see docs/04-structural/ARCHITECT_CHECKLIST.md Phase 0
 */

// =============================================================================
// Core Types (match BacktestChart props)
// Per CODING_STANDARDS: plain object shapes use `type` (closed, no merging).
// =============================================================================

/** Scalar values inside `indicator_groups` buckets (aligns with API `CandleResponse`). */
type SignalChartIndicatorScalar = number | string | boolean;

export type SignalChartIndicatorGroups = Record<string, Record<string, SignalChartIndicatorScalar>>;

export type SignalChartCandle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  /**
   * Parity/debug: grouped indicators from BE (`indicator_groups`), e.g. `p0_exact`.
   */
  indicator_groups?: SignalChartIndicatorGroups | null;
  /** ML backtest: model input feature name → value (same as predict_proba row). */
  model_features?: Record<string, number> | null;
  /**
   * ML/hybrid backtest: model class at this bar (from API `candle.ml_prediction`).
   * Includes HOLD, which is omitted from chart `predictions` derived from `signals`.
   */
  ml_prediction?: 'BUY' | 'SELL' | 'HOLD' | null;
  /** ML/hybrid: confidence for `ml_prediction`, percent 0–100 (`candle.ml_confidence_percent`). */
  ml_confidence_percent?: number | null;
};

export type SignalChartSignal = {
  timestamp: string;
  type: 'BUY' | 'SELL' | 'EXIT';
  price: number;
  confidence?: number;
  reason?: string;
  side?: 'long' | 'short';
  /** Chart DRY plan: hover text when present (ENTRY: entry_fee; EXIT: net_pnl, exit_fee) */
  entry_fee?: number;
  exit_fee?: number;
  net_pnl?: number;
  /** Absolute SL price for TP/SL zone visualization (from backtester). */
  stop_loss_price?: number;
  /** Absolute TP price for TP/SL zone visualization (from backtester). */
  take_profit_price?: number;
  /** TP1/min TP for banded overlays (trading_bots parity). */
  min_tp_price?: number;
  /** 1R price target for banded overlays (trading_bots parity). */
  tp_1r_price?: number;
  /** TP2/full TP for banded overlays (trading_bots parity). */
  full_tp_price?: number;
  /** Theoretical isolated liq touch price when reason=liquidation (perp overlay). */
  theoretical_liquidation_price?: number;
  /** Dynamic TP/SL volatility regime resolved by backtester (low|mid|high). */
  dynamic_volatility_regime?: 'low' | 'mid' | 'high';
};

export type SignalChartPrediction = {
  timestamp: string;
  type: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
};

export type SignalChartEquityPoint = {
  timestamp: string;
  value: number;
};

/**
 * One trace in multi-series equity overlay (strategy + buy-and-hold baselines).
 */
export type EquityOverlaySeriesItem = {
  name: string;
  points: SignalChartEquityPoint[];
  color: string;
  dash?: 'solid' | 'dash';
};

/** RSI indicator point (single timestamp). */
export type SignalChartRSIPoint = {
  timestamp: string;
  value: number;
};

/** MACD indicator point (single timestamp). */
export type SignalChartMACDPoint = {
  timestamp: string;
  macd: number;
  signal: number;
  histogram: number;
};

/** Bollinger Bands point (single timestamp). */
export type SignalChartBollingerBandPoint = {
  timestamp: string;
  upper: number;
  middle: number;
  lower: number;
};

// =============================================================================
// Canonical Contract
// =============================================================================

export type SignalChartData = {
  candles: SignalChartCandle[];
  signals: SignalChartSignal[];
  predictions?: SignalChartPrediction[];
  equityCurve?: SignalChartEquityPoint[];
  symbol: string;
  timeframe: string;
  /**
   * When true (ML/Hybrid backtest run), candlestick hover includes prediction / confidence.
   * Model feature vectors are not shown in the Plotly tooltip.
   */
  chartMlModelHover?: boolean;
  /** Optional indicators (RSI, MACD, Bollinger) from signal_chart.json */
  rsi?: SignalChartRSIPoint[];
  macd?: SignalChartMACDPoint[];
  bollingerBands?: SignalChartBollingerBandPoint[];
  /** Model detail only: whether HTML chart is available for "Open Full Chart" */
  hasHtmlChart?: boolean;
};
