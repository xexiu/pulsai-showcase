// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { resolveLiquidationHeatmapDisplayIntensity } from '@/utils/chart-liquidation-heatmap-intensity';

describe('resolveLiquidationHeatmapDisplayIntensity', () => {
  it('uses leverage-tier weights when all USD intensities are identical (OI estimate)', () => {
    const bands = [
      { price: 90_000, intensityUsd: 5_000_000, side: 'long' as const, leverageTier: 5 },
      { price: 88_000, intensityUsd: 5_000_000, side: 'long' as const, leverageTier: 100 },
    ];

    const weights = resolveLiquidationHeatmapDisplayIntensity(bands);

    expect(weights.get('90000:5:long')).toBe(0);
    expect(weights.get('88000:100:long')).toBe(1);
  });

  it('sqrt-scales varying vendor intensities for perceptual spread', () => {
    const bands = [
      { price: 100, intensityUsd: 100, side: 'long' as const, leverageTier: null },
      { price: 200, intensityUsd: 400, side: 'short' as const, leverageTier: null },
    ];

    const weights = resolveLiquidationHeatmapDisplayIntensity(bands);

    expect(weights.get('100:na:long')).toBeCloseTo(0.5);
    expect(weights.get('200:na:short')).toBe(1);
  });
});
