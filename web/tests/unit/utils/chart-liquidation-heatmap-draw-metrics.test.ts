// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  resolveLiquidationHeatmapBandAlpha,
  resolveLiquidationHeatmapBandThicknessPx,
  resolveLiquidationHeatmapVerticalBarWidthPx,
} from '@/utils/chart-liquidation-heatmap-draw-metrics';
import {
  LIQUIDATION_HEATMAP_BAND_ALPHA_DEFAULT,
  LIQUIDATION_HEATMAP_BAND_ALPHA_MAX,
  LIQUIDATION_HEATMAP_BAND_ALPHA_MIN,
  LIQUIDATION_HEATMAP_DEFAULT_BAND_HEIGHT_PX,
  LIQUIDATION_HEATMAP_VERTICAL_BAR_MAX_WIDTH_PX,
} from '@/utils/constants/chartLiquidationHeatmap';

describe('chart liquidation heatmap draw metrics', () => {
  it('maps mid intensity to default alpha 0.5', () => {
    expect(resolveLiquidationHeatmapBandAlpha(0.5)).toBe(LIQUIDATION_HEATMAP_BAND_ALPHA_DEFAULT);
  });

  it('maps zero and full intensity to alpha bounds', () => {
    expect(resolveLiquidationHeatmapBandAlpha(0)).toBe(LIQUIDATION_HEATMAP_BAND_ALPHA_MIN);
    expect(resolveLiquidationHeatmapBandAlpha(1)).toBe(LIQUIDATION_HEATMAP_BAND_ALPHA_MAX);
  });

  it('scales horizontal band thickness with intensity', () => {
    const weak = resolveLiquidationHeatmapBandThicknessPx(
      LIQUIDATION_HEATMAP_DEFAULT_BAND_HEIGHT_PX,
      0
    );
    const strong = resolveLiquidationHeatmapBandThicknessPx(
      LIQUIDATION_HEATMAP_DEFAULT_BAND_HEIGHT_PX,
      1
    );

    expect(weak).toBeLessThan(strong);
    expect(weak).toBeGreaterThanOrEqual(1);
  });

  it('scales vertical bar width with intensity', () => {
    const weak = resolveLiquidationHeatmapVerticalBarWidthPx(0);
    const strong = resolveLiquidationHeatmapVerticalBarWidthPx(1);

    expect(weak).toBeLessThan(strong);
    expect(strong).toBeLessThanOrEqual(LIQUIDATION_HEATMAP_VERTICAL_BAR_MAX_WIDTH_PX);
    expect(weak).toBeGreaterThanOrEqual(1);
  });

  it('clamps out-of-range intensity inputs', () => {
    expect(resolveLiquidationHeatmapBandAlpha(-1)).toBe(LIQUIDATION_HEATMAP_BAND_ALPHA_MIN);
    expect(resolveLiquidationHeatmapBandAlpha(2)).toBe(LIQUIDATION_HEATMAP_BAND_ALPHA_MAX);
  });
});
