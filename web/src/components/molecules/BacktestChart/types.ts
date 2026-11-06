/**
 * BacktestChart types — uses canonical signal-chart types (Chart DRY plan).
 *
 * @see docs/04-structural/CODING_STANDARDS.md
 * @see @/types/signal-chart
 */

import type {
  SignalChartBollingerBandPoint,
  SignalChartCandle,
  SignalChartEquityPoint,
  SignalChartMACDPoint,
  SignalChartPrediction,
  SignalChartRSIPoint,
  SignalChartSignal,
} from '@/types/signal-chart';

// Aliases for hook/component usage (canonical types)
export type Candle = SignalChartCandle;
export type Signal = SignalChartSignal;
export type Prediction = SignalChartPrediction;
export type EquityPoint = SignalChartEquityPoint;

type RSIPoint = SignalChartRSIPoint;
type MACDPoint = SignalChartMACDPoint;
type BollingerBandPoint = SignalChartBollingerBandPoint;

export type BacktestChartProps = {
  candles: Candle[];
  signals: Signal[];
  predictions?: Prediction[];
  equityCurve?: EquityPoint[];
  symbol: string;
  timeframe: string;
  showEquityCurve?: boolean;
  height?: number;
  rsi?: RSIPoint[] | undefined;
  macd?: MACDPoint[] | undefined;
  bollingerBands?: BollingerBandPoint[] | undefined;
  /**
   * When true, candlestick hover includes ml_prediction / ml_confidence_percent
   * (model feature vectors are not dumped into the Plotly tooltip).
   */
  chartMlModelHover?: boolean;
  /**
   * Optional override for x-axis title context (IANA). When omitted, `BacktestChart` uses
   * `useChartTimezonePreference()` so the label matches the dashboard/full chart zone.
   */
  chartDisplayTimezone?: string;
  /** Global backtest chart toggle: show 1R/minTP guide overlays. */
  showRLevelGuides?: boolean;
  /** Perp liquidation overlay: theoretical liq line + slippage gap to fill. */
  showLiquidationGuides?: boolean;
  /** Historical liquidation heatmap bands at each trade entry (no lookahead). */
  showLiquidationHeatmap?: boolean;
  /** Global backtest chart toggle: show dynamic volatility regime entry hints. */
  showDynamicRegimeHints?: boolean;
};
