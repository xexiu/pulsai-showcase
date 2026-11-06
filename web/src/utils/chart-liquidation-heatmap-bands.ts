/**
 * Filter + normalize liquidation heatmap bands for the LWC primitive.
 */

import type {
  LiquidationHeatmapBand,
  LiquidationHeatmapBandDrawSpec,
  LiquidationHeatmapResponse,
} from '@/types/chart-liquidation-heatmap';
import { resolveLiquidationHeatmapBandAlpha } from '@/utils/chart-liquidation-heatmap-draw-metrics';
import {
  liquidationHeatmapBandDrawKey,
  resolveLiquidationHeatmapDisplayIntensity,
} from '@/utils/chart-liquidation-heatmap-intensity';
import {
  LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS,
  type LiquidationHeatmapOverlayPreferences,
} from '@/utils/constants/chartLiquidationHeatmap';

function passesFilters(
  band: LiquidationHeatmapBand,
  preferences: LiquidationHeatmapOverlayPreferences
): boolean {
  if (band.intensityUsd < preferences.minIntensityUsd) {
    return false;
  }

  if (
    band.leverageTier != null &&
    !(preferences.leverageTiers as readonly number[]).includes(band.leverageTier)
  ) {
    return false;
  }

  return true;
}

/**
 * Single-shot memo keyed on the snapshot ref (leak-free via WeakMap). The unified-sync
 * revision builder and the apply step call this with the same (snapshot, preferences) refs
 * in the same tick — the cache turns that double call into one filter+normalize pass.
 */
const drawSpecCache = new WeakMap<
  LiquidationHeatmapResponse,
  { preferences: LiquidationHeatmapOverlayPreferences; specs: LiquidationHeatmapBandDrawSpec[] }
>();

export function selectLiquidationHeatmapBandsForDraw(
  snapshot: LiquidationHeatmapResponse | null | undefined,
  preferences: LiquidationHeatmapOverlayPreferences
): LiquidationHeatmapBandDrawSpec[] {
  if (!preferences.show || snapshot == null || snapshot.bands.length === 0) {
    return [];
  }

  const cached = drawSpecCache.get(snapshot);

  if (cached && cached.preferences === preferences) {
    return cached.specs;
  }

  const filtered = snapshot.bands.filter((band) => passesFilters(band, preferences));
  const displayIntensityByKey = resolveLiquidationHeatmapDisplayIntensity(filtered);

  const specs = filtered.map((band) => {
    const normalizedIntensity = displayIntensityByKey.get(liquidationHeatmapBandDrawKey(band)) ?? 0;
    const alpha = resolveLiquidationHeatmapBandAlpha(normalizedIntensity);

    return {
      price: band.price,
      intensityUsd: band.intensityUsd,
      normalizedIntensity,
      side: band.side,
      leverageTier: band.leverageTier,
      fillStyle: `rgba(${LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS[band.side]}, ${alpha})`,
    };
  });

  drawSpecCache.set(snapshot, { preferences, specs });

  return specs;
}
