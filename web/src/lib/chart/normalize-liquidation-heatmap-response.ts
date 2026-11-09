/**
 * Normalize liquidation heatmap API wire DTO to camelCase view model.
 */

import type {
  LiquidationHeatmapBand,
  LiquidationHeatmapBandSide,
  LiquidationHeatmapResponse,
  RawLiquidationHeatmapResponse,
} from '@/types/chart-liquidation-heatmap';

function normalizeSide(side: string): LiquidationHeatmapBandSide {
  if (side === 'long' || side === 'short') {
    return side;
  }

  return 'unknown';
}

function normalizeBand(
  raw: RawLiquidationHeatmapResponse['bands'][number]
): LiquidationHeatmapBand {
  return {
    price: raw.price,
    intensityUsd: raw.intensity_usd,
    side: normalizeSide(raw.side),
    leverageTier: raw.leverage_tier,
  };
}

export function normalizeLiquidationHeatmapResponse(
  raw: RawLiquidationHeatmapResponse
): LiquidationHeatmapResponse {
  return {
    provider: raw.provider,
    quality: raw.quality,
    asOfMs: raw.as_of_ms,
    symbol: raw.symbol,
    ccxtSymbol: raw.ccxt_symbol,
    exchange: raw.exchange,
    rangeLabel: raw.range_label,
    bands: raw.bands.map(normalizeBand),
    warnings: raw.warnings,
    cacheHit: raw.cache_hit,
    historicalSnapshot: raw.historical_snapshot ?? false,
    requestedAsOfMs: raw.requested_as_of_ms ?? null,
  };
}
