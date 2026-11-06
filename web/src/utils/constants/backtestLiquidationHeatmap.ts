/**
 * Backtest liquidation heatmap overlay draw preferences (no full-chart pref storage).
 */

import {
  LIQUIDATION_HEATMAP_DEFAULT_BAND_HEIGHT_PX,
  LIQUIDATION_HEATMAP_DEFAULT_RANGE,
  LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS,
  type LiquidationHeatmapOverlayPreferences,
} from '@/utils/constants/chartLiquidationHeatmap';

/**
 * Cap on concurrent per-entry historical heatmap fetches. Real backtests rarely exceed
 * this; the cap stops a pathological signal set (hundreds of entries) from firing a
 * thundering-herd of `useQueries` requests on first render. Entries beyond the cap render
 * without a heatmap overlay.
 */
export const BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS = 100;

/** Fixed draw prefs for backtest entry-window bands (toggle is separate). */
export const BACKTEST_LIQUIDATION_HEATMAP_DRAW_PREFERENCES: LiquidationHeatmapOverlayPreferences = {
  show: true,
  range: LIQUIDATION_HEATMAP_DEFAULT_RANGE,
  minIntensityUsd: 0,
  leverageTiers: LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS,
  bandHeightPx: LIQUIDATION_HEATMAP_DEFAULT_BAND_HEIGHT_PX,
  useVerticalBars: false,
};
