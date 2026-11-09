/**
 * ML prediction marker x-axis anchor (LWC dashboard / full chart / trade).
 *
 * Default: **bar open** UTC — matches Plotly backtest + row join key (`Signal.timestamp`).
 *
 * Legacy (opt-out): BE bar open + **one timeframe** on the axis (close-instant placement).
 *
 * Env `NEXT_PUBLIC_CHART_ML_PREDICTION_MARKER_USE_BAR_OPEN_ONLY` (build-time):
 * - unset or `true` → bar-open anchor
 * - `false` → legacy (`open + 1×timeframe`)
 *
 * @see docs/08-adr/ADR-016-chart-ml-prediction-marker-anchor.md
 */

import { getTimeframeSeconds } from '@/utils/chart-time';

export type ChartMlPredictionMarkerAnchorMode = 'legacy_close_instant' | 'bar_open';

export function resolveChartMlPredictionMarkerAnchorMode(): ChartMlPredictionMarkerAnchorMode {
  const raw = process.env['NEXT_PUBLIC_CHART_ML_PREDICTION_MARKER_USE_BAR_OPEN_ONLY'];

  if (raw === 'false') {
    return 'legacy_close_instant';
  }

  return 'bar_open';
}

/** True when markers / tooltip should use bar open UTC (no +1 TF shift). */
export function resolveChartMlPredictionMarkerUseBarOpenOnly(): boolean {
  return resolveChartMlPredictionMarkerAnchorMode() === 'bar_open';
}

/**
 * Chart x for ML prediction: either bar open UTC or legacy open+period (close instant).
 */
export function resolveMlPredictionChartBarOpenUtc(
  barOpenUtcSec: number,
  timeframe: string
): number {
  if (resolveChartMlPredictionMarkerUseBarOpenOnly()) {
    return barOpenUtcSec;
  }

  const periodSec = getTimeframeSeconds(timeframe);

  return periodSec > 0 ? barOpenUtcSec + periodSec : barOpenUtcSec;
}
