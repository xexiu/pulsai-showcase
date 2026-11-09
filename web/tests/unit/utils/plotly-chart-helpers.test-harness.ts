/**
 * Shared plotly chart test harness (DRY across split test files).
 */

import type { CandleData, SignalData } from '@/utils/plotly-chart-helpers';
import { timestampToPlotlyXMs } from '@/utils/plotly-chart-time';

/** Drill into Plotly trace/layout objects in tests without `any`. */
export function plotlyDeep(obj: unknown, ...path: string[]): unknown {
  let cur: unknown = obj;

  for (const key of path) {
    cur = (cur as Record<string, unknown>)[key];
  }

  return cur;
}

/** Plotly x: real UTC epoch ms (chartTimezone unused; kept for PlotlyTimeOptions shape). */
export const PLOTLY_UTC_1H = { chartTimezone: 'UTC', timeframe: '1h' } as const;

export function px(iso: string): number {
  return timestampToPlotlyXMs(iso, PLOTLY_UTC_1H.chartTimezone, PLOTLY_UTC_1H.timeframe);
}

export const mockCandles: CandleData[] = [
  { timestamp: '2026-01-01T00:00:00Z', open: 100, high: 110, low: 95, close: 105 },
  { timestamp: '2026-01-01T01:00:00Z', open: 105, high: 115, low: 100, close: 110 },
];

export const mockSignals: SignalData[] = [
  { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', price: 100, confidence: 85 },
  { timestamp: '2026-01-01T01:00:00Z', type: 'SELL', price: 110, confidence: 75 },
];
