/**
 * Intensity-driven draw metrics for liquidation heatmap bands (opacity + thickness).
 */

import {
  LIQUIDATION_HEATMAP_BAND_ALPHA_MAX,
  LIQUIDATION_HEATMAP_BAND_ALPHA_MIN,
  LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MAX,
  LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MIN,
  LIQUIDATION_HEATMAP_VERTICAL_BAR_MAX_WIDTH_PX,
} from '@/utils/constants/chartLiquidationHeatmap';

function clampNormalizedIntensity(normalizedIntensity: number): number {
  return Math.min(1, Math.max(0, normalizedIntensity));
}

function resolveThicknessScale(normalizedIntensity: number): number {
  const clamped = clampNormalizedIntensity(normalizedIntensity);

  return (
    LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MIN +
    clamped *
      (LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MAX - LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MIN)
  );
}

export function resolveLiquidationHeatmapBandAlpha(normalizedIntensity: number): number {
  const clamped = clampNormalizedIntensity(normalizedIntensity);

  return (
    LIQUIDATION_HEATMAP_BAND_ALPHA_MIN +
    clamped * (LIQUIDATION_HEATMAP_BAND_ALPHA_MAX - LIQUIDATION_HEATMAP_BAND_ALPHA_MIN)
  );
}

export function resolveLiquidationHeatmapBandThicknessPx(
  baseBandHeightPx: number,
  normalizedIntensity: number
): number {
  return Math.max(1, baseBandHeightPx * resolveThicknessScale(normalizedIntensity));
}

export function resolveLiquidationHeatmapVerticalBarWidthPx(normalizedIntensity: number): number {
  const scale = resolveThicknessScale(normalizedIntensity);

  return Math.max(
    1,
    (LIQUIDATION_HEATMAP_VERTICAL_BAR_MAX_WIDTH_PX * scale) /
      LIQUIDATION_HEATMAP_BAND_THICKNESS_SCALE_MAX
  );
}
