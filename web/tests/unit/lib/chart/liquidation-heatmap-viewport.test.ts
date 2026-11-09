// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  LIQUIDATION_HEATMAP_RANGE_DURATION_MS,
  chartVisibleWindowMs,
  minRangeCoveringWindowMs,
  resolveLiquidationHeatmapViewportRange,
} from '@/lib/chart/liquidation-heatmap-viewport';

const H = 3_600_000;
const D = 24 * H;

describe('liquidation-heatmap-viewport', () => {
  /**
   * Value-lock: if BE liquidation_heatmap_range_duration.py changes, update here too.
   * TypeScript exhaustiveness (Record<LiquidationHeatmapRangeLabel, number>) catches
   * new keys; this test catches numeric drift.
   */
  it('LIQUIDATION_HEATMAP_RANGE_DURATION_MS mirrors BE range ladder', () => {
    expect(LIQUIDATION_HEATMAP_RANGE_DURATION_MS).toEqual({
      '12h': 12 * H,
      '24h': 24 * H,
      '3d': 3 * D,
      '7d': 7 * D,
      '30d': 30 * D,
      '90d': 90 * D,
      '180d': 180 * D,
      '1y': 365 * D,
    });
  });

  it('computes visible window from timeframe and candle count', () => {
    expect(chartVisibleWindowMs('5m', 12)).toBe(3_600_000);
  });

  it('picks smallest range covering the window', () => {
    expect(minRangeCoveringWindowMs(3_600_000)).toBe('12h');
    expect(minRangeCoveringWindowMs(30 * 24 * 3_600_000)).toBe('30d');
  });

  it('bumps user range when shorter than visible window', () => {
    expect(resolveLiquidationHeatmapViewportRange('12h', '1h', 24)).toBe('24h');
    expect(resolveLiquidationHeatmapViewportRange('24h', '1h', 24)).toBe('24h');
  });
});
