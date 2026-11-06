/**
 * Display intensity for liquidation heatmap bands (opacity + thickness driver).
 *
 * Vendor snapshots: sqrt-scaled USD intensity for perceptual spread.
 * OI-leverage estimate: identical per-band USD — fallback to leverage-tier weight.
 */

import type { LiquidationHeatmapBand } from '@/types/chart-liquidation-heatmap';
import { LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS } from '@/utils/constants/chartLiquidationHeatmap';

/** Relative spread below which USD intensities are treated as uniform (OI estimate). */
const UNIFORM_INTENSITY_RELATIVE_EPSILON = 0.001;

export function liquidationHeatmapBandDrawKey(band: LiquidationHeatmapBand): string {
  return `${band.price}:${band.leverageTier ?? 'na'}:${band.side}`;
}

function hasUniformUsdIntensity(bands: readonly LiquidationHeatmapBand[]): boolean {
  if (bands.length <= 1) {
    return true;
  }

  const intensities = bands.map((band) => band.intensityUsd);
  const max = Math.max(...intensities);
  const min = Math.min(...intensities);

  if (max <= 0) {
    return true;
  }

  return (max - min) / max < UNIFORM_INTENSITY_RELATIVE_EPSILON;
}

function leverageTierVisualWeight(leverageTier: number | null): number {
  if (leverageTier == null) {
    return 0.5;
  }

  const index = (LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS as readonly number[]).indexOf(
    leverageTier
  );

  if (index < 0) {
    return 0.5;
  }

  const maxIndex = LIQUIDATION_HEATMAP_LEVERAGE_TIER_OPTIONS.length - 1;

  if (maxIndex <= 0) {
    return 1;
  }

  return index / maxIndex;
}

function sqrtNormalizedUsdIntensity(intensityUsd: number, maxIntensityUsd: number): number {
  if (maxIntensityUsd <= 0 || intensityUsd <= 0) {
    return 0;
  }

  const linear = intensityUsd / maxIntensityUsd;

  return Math.sqrt(linear);
}

/**
 * Map each band to [0, 1] display intensity for draw metrics.
 */
export function resolveLiquidationHeatmapDisplayIntensity(
  bands: readonly LiquidationHeatmapBand[]
): Map<string, number> {
  if (bands.length === 0) {
    return new Map();
  }

  const maxIntensityUsd = bands.reduce((acc, band) => Math.max(acc, band.intensityUsd), 0);

  if (maxIntensityUsd <= 0) {
    return new Map(bands.map((band) => [liquidationHeatmapBandDrawKey(band), 0]));
  }

  if (hasUniformUsdIntensity(bands)) {
    return new Map(
      bands.map((band) => [
        liquidationHeatmapBandDrawKey(band),
        leverageTierVisualWeight(band.leverageTier),
      ])
    );
  }

  return new Map(
    bands.map((band) => [
      liquidationHeatmapBandDrawKey(band),
      sqrtNormalizedUsdIntensity(band.intensityUsd, maxIntensityUsd),
    ])
  );
}
