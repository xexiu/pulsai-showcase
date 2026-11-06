/**
 * Plotly backtest chart types (shared with layout helpers).
 */

import type { PlotlyTraceData } from '@/types/plotly-layout';
import type { SignalChartIndicatorGroups } from '@/types/signal-chart';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

export interface ThemeColors {
  paper: string;
  plot: string;
  grid: string;
  line: string;
  text: string;
  textMuted: string;
  bullish: string;
  bearish: string;
  signal: string;
  /** Brand-aligned equity / cumulative P&L stroke (see `--chart-equity-line`). */
  equityCurveLine: string;
}

/** @deprecated Prefer PlotlyTraceData from @/types/plotly-layout */
export type PlotlyData = PlotlyTraceData;

export type RSIData = Array<{ timestamp: string; value: number }>;
export type MACDData = Array<{
  timestamp: string;
  macd: number;
  signal: number;
  histogram: number;
}>;
export type BBData = Array<{ timestamp: string; upper: number; middle: number; lower: number }>;

export interface CandleData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  indicator_groups?: SignalChartIndicatorGroups | null;
  model_features?: Record<string, number> | null;
  ml_prediction?: 'BUY' | 'SELL' | 'HOLD' | null;
  ml_confidence_percent?: number | null;
}

export interface SignalData {
  timestamp: string;
  type: 'BUY' | 'SELL' | 'EXIT';
  price: number;
  confidence?: number;
  reason?: string;
  /** For EXIT: 'long' = sell-to-close (red), 'short' = buy-to-close (green). ADR-015 */
  side?: 'long' | 'short';
  /** Chart DRY plan: hover text when present */
  entry_fee?: number;
  exit_fee?: number;
  net_pnl?: number;
  stop_loss?: number;
  take_profit?: number;
  /** Absolute SL price from backtester (TP/SL zone visualization). */
  stop_loss_price?: number;
  /** Absolute TP price from backtester (TP/SL zone visualization). */
  take_profit_price?: number;
  /** TP1/min TP from backtester (banded TP visualization). */
  min_tp_price?: number;
  /** 1R target from backtester (banded TP visualization). */
  tp_1r_price?: number;
  /** TP2/full TP from backtester (banded TP visualization). */
  full_tp_price?: number;
  /** Theoretical isolated liq touch when reason=liquidation (perp chart overlay). */
  theoretical_liquidation_price?: number;
  /** Dynamic TP/SL volatility regime resolved by backtester (low|mid|high). */
  dynamic_volatility_regime?: string;
}

interface PredictionData {
  timestamp: string;
  type: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
}

export interface EquityData {
  timestamp: string;
  value: number;
}

export interface LayoutOptions {
  symbol: string;
  timeframe: string;
  showEquityCurve: boolean;
  hasRSI: boolean;
  hasMACD: boolean;
  colors: ThemeColors;
  /**
   * IANA zone from chart preference (same as LWC dashboard/full chart).
   * Plotly x values stay UTC ms; this only adjusts the x-axis title for parity context.
   */
  chartDisplayTimezone?: string;
  chartHeight?: number;
}

/** Optional Plotly candlestick trace behavior (backtest ML hover parity). */
export type CandlestickTraceOptions = {
  /** When true, candle hover includes inline ml_prediction / ml_confidence_percent. */
  chartMlModelHover?: boolean;
};

/** Single-parameter shape for :func:`createPredictionData` (keeps eslint max-params satisfied). */
export type CreatePredictionDataParams = {
  predictions: PredictionData[];
  type: 'BUY' | 'SELL' | 'HOLD';
  candles: CandleData[];
  colors: ThemeColors;
  plotlyTime: PlotlyTimeOptions;
  /**
   * Reserved for call-site parity with candlestick/signal ML hover wiring.
   * Prediction-dot hover always shows type + confidence (model features omitted).
   */
  chartMlModelHover?: boolean;
};
