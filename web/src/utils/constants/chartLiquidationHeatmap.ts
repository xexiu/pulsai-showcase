/**
 * Liquidation heatmap overlay — FE SoT (prefs, ranges, colors, API defaults).
 *
 * @see docs/02-technical/LIQUIDATION_HEATMAP_CHART_ARCHITECT_TODO.md
 * @see apps/api/src/shared/constants/liquidation_heatmap.py
 */

import type { LiquidationHeatmapBandSide } from '@/types/chart-liquidation-heatmap';

/** Coinglass exchange label sent to GET /market/liquidation-heatmap. */
export const LIQUIDATION_HEATMAP_DEFAULT_EXCHANGE = 'Binance' as const;

/** Default lookback when user has not changed range pref. */
export const LIQUIDATION_HEATMAP_DEFAULT_RANGE = '24h' as const;

/** Mirrors BE LIQUIDATION_HEATMAP_COINGLASS_RANGES. */
export const LIQUIDATION_HEATMAP_RANGE_OPTIONS = [
  '12h',
  '24h',
  '3d',
  '7d',
  '30d',
  '90d',
  '180d',
  '1y',
] as const;

export type LiquidationHeatmapRangeLabel = (typeof LIQUIDATION_HEATMAP_RANGE_OPTIONS)[number];

/** Leverage tiers for filter UI (matches BE estimator). */
// eslint-disable-next-line @typescript-eslint/no-magic-numbers -- Binance tier ladder (BE SoT)
export const LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS = [5, 10, 25, 50, 100] as const;

type LiquidationHeatmapLeverageTier = (typeof LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS)[number];

/** Default horizontal band thickness in CSS pixels (scaled by intensity at draw time). */
export const LIQUIDATION_HEATMAP_DEFAULT_BAND_HEIGHT_PX = 4;

/** Max right-edge bar width in vertical (Coinglass-style) mode. */
export const LIQUIDATION_HEATMAP_VERTICAL_BAR_MAX_WIDTH_PX = 80;

/** Default render mode — horizontal bands; opt in to Coinglass-style right-edge vertical bars. */
export const LIQUIDATION_HEATMAP_DEFAULT_USE_VERTICAL_BARS = false;

/** Min intensity (USD) floor for drawing bands (user pref default). */
const LIQUIDATION_HEATMAP_DEFAULT_MIN_INTENSITY_USD = 0;

/** Step (USD) for the min-intensity number input in the prefs panel. */
export const LIQUIDATION_HEATMAP_MIN_INTENSITY_STEP_USD = 100_000;

/** Mobile viewport auto-groups sparse bands by raising min intensity (PDF §16–19). */
export const LIQUIDATION_HEATMAP_MOBILE_AUTO_GROUP_MIN_INTENSITY_USD = 500_000;

/** Scalping preset — 100x tier only (mirrors BE LIQUIDATION_HEATMAP_SCALPING_LEVERAGE_TIERS). */
export const LIQUIDATION_HEATMAP_SCALPING_LEVERAGE_TIERS = [100] as const;

/** Debounce overlay sync while forming candle ticks (ms). */
export const LIQUIDATION_HEATMAP_FORMING_CANDLE_DEBOUNCE_MS = 300;

/**
 * How long the API considers a vendor snapshot current — its Redis TTL and the age at which it
 * relabels the snapshot `stale`. The overlay refreshes on THIS cadence rather than on candle close,
 * because the map is a picture of current open interest, not a per-bar value: on 1d it would move
 * once a day, and on 5m it would lag the data it draws.
 *
 * Mirrors BE LIQUIDATION_HEATMAP_VENDOR_CACHE_TTL_S; pinned by
 * tests/unit/utils/constants/chartLiquidationHeatmap.parity.test.ts.
 */
export const LIQUIDATION_HEATMAP_VENDOR_TTL_MS = 120_000;

/**
 * The API holds estimated/degraded snapshots far longer than vendor ones, so the overlay backs off
 * to this cadence during a vendor outage instead of re-reading a value that cannot have changed.
 *
 * Mirrors BE LIQUIDATION_HEATMAP_DEGRADED_CACHE_TTL_S; pinned by the same parity test.
 */
export const LIQUIDATION_HEATMAP_DEGRADED_TTL_MS = 600_000;

/**
 * Floor for the refresh delay. An expired or clock-skewed snapshot would otherwise resolve to a
 * non-positive delay, which TanStack reads as "stop polling" — and anything faster than this spends
 * the endpoint's 30 req/min cap (BE market_liquidation_heatmap_rate_limit_per_minute) on a value the
 * server is still caching. 15s = at most 4 req/min per open chart.
 */
export const LIQUIDATION_HEATMAP_MIN_REFETCH_INTERVAL_MS = 15_000;

export const LIQUIDATION_HEATMAP_STORAGE_KEY_PREFIX = 'pulsai_liquidation_heatmap_prefs' as const;

export const LIQUIDATION_HEATMAP_QUALITY_BADGE_TEST_ID =
  'liquidation-heatmap-quality-badge' as const;

export type { LiquidationHeatmapQualityId } from '@/types/chart-liquidation-heatmap';

/** Opacity bounds — mid intensity (0.5) maps to LIQUIDATION_HEATMAP_BAND_ALPHA_DEFAULT. */
export const LIQUIDATION_HEATMAP_BAND_ALPHA_MIN = 0.1;
export const LIQUIDATION_HEATMAP_BAND_ALPHA_MAX = 0.9;
export const LIQUIDATION_HEATMAP_BAND_ALPHA_DEFAULT = 0.5;

/** Thickness multiplier at min/max normalized intensity (applied to bandHeightPx / bar width). */
export const LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MIN = 0.35;
export const LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MAX = 2.75;

/**
 * Long/short liq band RGB channels (no alpha) — SoT for the canvas primitive and the
 * Plotly backtest shapes (both render the same Tailwind up/down family; alpha is applied
 * per-consumer from intensity). Long = red (below mark), short = green (above mark).
 *
 * NOTE: the derivatives-flow liq-history pane uses the Material indicator palette
 * (`chartDerivativesFlow.ts`) intentionally — do not merge it here.
 */
export const LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS = {
  long: '239, 68, 68',
  short: '34, 197, 94',
  unknown: '148, 163, 184',
} as const satisfies Record<LiquidationHeatmapBandSide, string>;

export type LiquidationHeatmapOverlayPreferences = {
  show: boolean;
  range: LiquidationHeatmapRangeLabel;
  minIntensityUsd: number;
  leverageTiers: readonly LiquidationHeatmapLeverageTier[];
  bandHeightPx: number;
  /** Coinglass-style right-edge bars when true; full-width horizontal bands when false. */
  useVerticalBars: boolean;
};

export const LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES: LiquidationHeatmapOverlayPreferences = {
  /**
   * ON for everyone, including a signed-out guest. Owner, 2026-09-14: "we should ALWAYS shouw
   * (default on) the ST (storachasting indicator) and liquidity map ... so guest and/or free users
   * can get those 2 as 'free'".
   *
   * It costs nothing against the plan's indicator cap — the map is not a `ChartIndicatorPreferences`
   * key, so `countEnabledIndicators` never sees it. The half that DID need work was the door:
   * GET /market/liquidation-heatmap answered 401 to a guest until it was opened the same day.
   */
  show: true,
  range: LIQUIDATION_HEATMAP_DEFAULT_RANGE,
  minIntensityUsd: LIQUIDATION_HEATMAP_DEFAULT_MIN_INTENSITY_USD,
  leverageTiers: LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS,
  bandHeightPx: LIQUIDATION_HEATMAP_DEFAULT_BAND_HEIGHT_PX,
  useVerticalBars: LIQUIDATION_HEATMAP_DEFAULT_USE_VERTICAL_BARS,
};
