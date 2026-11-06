import { buildCandlestickHoverText } from '@/utils/plotly-chart-helpers/candlestick-hover-text';
import {
  createCompoundFillData,
  createSignalData,
} from '@/utils/plotly-chart-helpers/entry-traces';
import { createEquityData, createExitData } from '@/utils/plotly-chart-helpers/exit-traces';
import { createDynamicRegimeHintData } from '@/utils/plotly-chart-helpers/regime-traces';
import type {
  CandleData,
  CandlestickTraceOptions,
  PlotlyData,
  ThemeColors,
} from '@/utils/plotly-chart-helpers/types';
import { mapTimestampForPlotlyTrace, type PlotlyTimeOptions } from '@/utils/plotly-chart-time';

export { buildSignalMlHoverText } from '@/utils/plotly-chart-helpers/signal-ml-hover';
export {
  createSignalData,
  createCompoundFillData,
  createExitData,
  createEquityData,
  createDynamicRegimeHintData,
};
/**
 * Create candlestick (OHLC) chart data for Plotly.
 *
 * Sorts by timestamp - Plotly requires chronological x-axis.
 * Unsorted candles cause overlapping/duplicated visual.
 *
 * Hover starts with **Bar open** / **Bar close** (wall time in `plotlyTime.chartTimezone`; close
 * from open + timeframe when TF is known), then OHLC
 * (parity with trading_bots PRICE_INFO: open_date then open/high/low/close prices).
 *
 * When `traceOptions.chartMlModelHover` is true, hover also includes optional
 * inline `ml_prediction` / `ml_confidence_percent` (model feature vectors omitted).
 */
export function createCandlestickData(
  candles: CandleData[],
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions,
  traceOptions?: CandlestickTraceOptions
): PlotlyData | null {
  if (!candles || candles.length === 0) {
    return null;
  }

  const sorted = [...candles].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  const chartMlModelHover = traceOptions?.chartMlModelHover === true;

  return {
    type: 'candlestick',
    name: 'Price',
    xaxis: 'x',
    yaxis: 'y',
    x: sorted.map((c) => mapTimestampForPlotlyTrace(c.timestamp, plotlyTime)),
    open: sorted.map((c) => c.open),
    high: sorted.map((c) => c.high),
    low: sorted.map((c) => c.low),
    close: sorted.map((c) => c.close),
    increasing: { line: { color: colors.bullish } },
    decreasing: { line: { color: colors.bearish } },
    hovertext: sorted.map((c) => buildCandlestickHoverText(c, chartMlModelHover, plotlyTime)),
    hoverinfo: 'text',
  };
}
