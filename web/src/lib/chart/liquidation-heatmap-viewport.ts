/**
 * Viewport-aware heatmap range + mobile grouping helpers (FE SoT).
 *
 * @see docs/02-technical/LIQUIDATION_HEATMAP_CHART_ARCHITECT_TODO.md
 */

import { TIMEFRAME_MS } from '@/utils/chart-time/timeframes';
import type { ChartTimeframe } from '@/utils/chart-time/types';
import {
  LIQUIDATION_HEATMAP_RANGE_OPTIONS,
  type LiquidationHeatmapRangeLabel,
} from '@/utils/constants/chartLiquidationHeatmap';

/** Mirrors BE LIQUIDATION_HEATMAP_RANGE_DURATION_MS. */
const MS_PER_HOUR = 3_600_000;
const MS_PER_DAY = 24 * MS_PER_HOUR;

/* eslint-disable @typescript-eslint/no-magic-numbers -- mirrors BE range ladder (SoT) */
export const LIQUIDATION_HEATMAP_RANGE_DURATION_MS: Record<LiquidationHeatmapRangeLabel, number> = {
  '12h': 12 * MS_PER_HOUR,
  '24h': 24 * MS_PER_HOUR,
  '3d': 3 * MS_PER_DAY,
  '7d': 7 * MS_PER_DAY,
  '30d': 30 * MS_PER_DAY,
  '90d': 90 * MS_PER_DAY,
  '180d': 180 * MS_PER_DAY,
  '1y': 365 * MS_PER_DAY,
};
/* eslint-enable @typescript-eslint/no-magic-numbers */

/** Approximate visible chart span in ms from timeframe and candle count. */
export function chartVisibleWindowMs(timeframe: string, visibleCandleCount: number): number | null {
  if (visibleCandleCount < 1) {
    return null;
  }

  const tfMs = TIMEFRAME_MS[timeframe as ChartTimeframe];

  if (tfMs == null) {
    return null;
  }

  return tfMs * visibleCandleCount;
}

/** Smallest supported range label that covers the visible chart window. */
export function minRangeCoveringWindowMs(windowMs: number): LiquidationHeatmapRangeLabel {
  for (const range of LIQUIDATION_HEATMAP_RANGE_OPTIONS) {
    if (LIQUIDATION_HEATMAP_RANGE_DURATION_MS[range] >= windowMs) {
      return range;
    }
  }

  return LIQUIDATION_HEATMAP_RANGE_OPTIONS.at(-1) ?? '1y';
}

/**
 * Align heatmap lookback with visible candles: never fetch a shorter range than the chart window.
 */
export function resolveLiquidationHeatmapViewportRange(
  userRange: LiquidationHeatmapRangeLabel,
  timeframe: string,
  visibleCandleCount: number
): LiquidationHeatmapRangeLabel {
  const windowMs = chartVisibleWindowMs(timeframe, visibleCandleCount);

  if (windowMs == null) {
    return userRange;
  }

  const minRange = minRangeCoveringWindowMs(windowMs);
  const userDuration = LIQUIDATION_HEATMAP_RANGE_DURATION_MS[userRange];
  const minDuration = LIQUIDATION_HEATMAP_RANGE_DURATION_MS[minRange];

  return userDuration >= minDuration ? userRange : minRange;
}
