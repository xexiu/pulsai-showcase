/**
 * Build GET /api/v1/market/liquidation-heatmap query URL.
 */

import {
  LIQUIDATION_HEATMAP_DEFAULT_EXCHANGE,
  LIQUIDATION_HEATMAP_DEFAULT_RANGE,
  type LiquidationHeatmapRangeLabel,
} from '@/utils/constants/chartLiquidationHeatmap';

export type BuildLiquidationHeatmapRequestUrlParams = {
  symbol: string;
  exchange?: string;
  range?: LiquidationHeatmapRangeLabel;
  asOfMs?: number;
  timeframe?: string;
  visibleCandleCount?: number;
};

export function buildLiquidationHeatmapRequestUrl({
  symbol,
  exchange = LIQUIDATION_HEATMAP_DEFAULT_EXCHANGE,
  range = LIQUIDATION_HEATMAP_DEFAULT_RANGE,
  asOfMs,
  timeframe,
  visibleCandleCount,
}: BuildLiquidationHeatmapRequestUrlParams): string {
  const params = new URLSearchParams({
    symbol,
    exchange,
    range,
  });

  if (asOfMs != null) {
    params.set('as_of_ms', String(asOfMs));
  }

  if (timeframe != null && timeframe.length > 0) {
    params.set('timeframe', timeframe);
  }

  if (visibleCandleCount != null && visibleCandleCount > 0) {
    params.set('visible_candle_count', String(visibleCandleCount));
  }

  return `/api/v1/market/liquidation-heatmap?${params.toString()}`;
}
