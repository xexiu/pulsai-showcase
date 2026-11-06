/**
 * Divergence pivot size per timeframe (chart display).
 *
 * importers/callers: `useIndicators` (dashboard / trade chart), the golden export script.
 * affected API: `getDivergencePivotLookbackBars(timeframe)` replaces `getDivergenceParamsForTimeframe`.
 * data schemas: none.
 *
 * Mirrors BE `chart_divergence_params.pivot_lookback_bars_for_timeframe` — the FE↔BE golden test
 * fails on drift.
 */

import type { ChartTimeframe } from '@/utils/chart-time/types';

/**
 * Bars a pivot must be strictly beyond on EACH side (TradingView `lbL` = `lbR`).
 *
 * TradingView's built-in default is 5 on every timeframe; the product keeps a smaller window on
 * the LTF band so a 5m pivot confirms in minutes, not an hour. That trade-off is a product
 * choice, not a derived value — a pivot's confirmation lag is exactly this many bars.
 */
const DIVERGENCE_PIVOT_LOOKBACK_BARS: Record<ChartTimeframe, number> = {
  '1m': 2,
  '3m': 2,
  '5m': 2,
  '15m': 2,
  '30m': 2,
  '1h': 3,
  '2h': 3,
  '4h': 4,
  '6h': 4,
  '8h': 4,
  '12h': 5,
  '1d': 5,
  '3d': 5,
  '1w': 5,
};

/** Fallback for an unknown timeframe: the 1h entry. */
const DEFAULT_DIVERGENCE_PIVOT_LOOKBACK_BARS = 3;

function isChartTimeframe(timeframe: string): timeframe is ChartTimeframe {
  return Object.hasOwn(DIVERGENCE_PIVOT_LOOKBACK_BARS, timeframe);
}

/**
 * Pivot size for divergence detection on `timeframe`.
 *
 * @example
 * getDivergencePivotLookbackBars('4h'); // 4
 */
export function getDivergencePivotLookbackBars(timeframe: string): number {
  if (!isChartTimeframe(timeframe)) {
    return DEFAULT_DIVERGENCE_PIVOT_LOOKBACK_BARS;
  }

  return DIVERGENCE_PIVOT_LOOKBACK_BARS[timeframe];
}
