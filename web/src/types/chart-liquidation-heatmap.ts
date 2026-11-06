/**
 * Types for GET /api/v1/market/liquidation-heatmap (full-chart overlay).
 */

/** Provider IDs from BE LiquidationHeatmapProviderId. */
type LiquidationHeatmapProviderId =
  | 'coinglass_model3'
  | 'oi_leverage_estimate'
  | 'liquidation_events'
  | 'unavailable';

/** Quality labels from BE LiquidationHeatmapQuality. */
export type LiquidationHeatmapQualityId =
  | 'vendor'
  | 'estimated'
  | 'degraded'
  | 'stale'
  | 'unavailable';

export type LiquidationHeatmapBandSide = 'long' | 'short' | 'unknown';

type RawLiquidationHeatmapBand = {
  price: number;
  intensity_usd: number;
  side: string;
  leverage_tier: number | null;
};

/** Wire DTO from FastAPI (snake_case). */
export type RawLiquidationHeatmapResponse = {
  provider: LiquidationHeatmapProviderId;
  quality: LiquidationHeatmapQualityId;
  as_of_ms: number;
  symbol: string;
  ccxt_symbol: string;
  exchange: string;
  range_label: string;
  bands: RawLiquidationHeatmapBand[];
  warnings: string[];
  cache_hit: boolean;
  historical_snapshot?: boolean;
  requested_as_of_ms?: number | null;
};

export type LiquidationHeatmapBand = {
  price: number;
  intensityUsd: number;
  side: LiquidationHeatmapBandSide;
  leverageTier: number | null;
};

export type LiquidationHeatmapResponse = {
  provider: LiquidationHeatmapProviderId;
  quality: LiquidationHeatmapQualityId;
  asOfMs: number;
  symbol: string;
  ccxtSymbol: string;
  exchange: string;
  rangeLabel: string;
  bands: LiquidationHeatmapBand[];
  warnings: readonly string[];
  cacheHit: boolean;
  historicalSnapshot: boolean;
  requestedAsOfMs: number | null;
};

/** Normalized band passed to the LWC primitive. */
export type LiquidationHeatmapBandDrawSpec = {
  price: number;
  intensityUsd: number;
  normalizedIntensity: number;
  side: LiquidationHeatmapBandSide;
  leverageTier: number | null;
  /** Precomputed `rgba(...)` fill (channels + intensity alpha) — avoids per-frame work. */
  fillStyle: string;
};
