/**
 * Per-timeframe classic indicator periods from GET /market/ohlcv and chart-indicators.
 * SoT: BE ``timeframe_indicator_configs`` (serialized as ``classic_indicator_config``).
 */

export type ClassicIndicatorConfig = {
  timeframe: string;
  rsi_period: number;
  macd_fast: number;
  macd_slow: number;
  macd_signal: number;
  bb_period: number;
  bb_std: number;
  divergence_lookback: number;
};
