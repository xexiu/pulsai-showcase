/**
 * useLiquidationHeatmapMobileGrouping — mobile min-intensity floor without mutating prefs.
 */

import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useLiquidationHeatmapMobileGrouping } from '@/hooks/useLiquidationHeatmapMobileGrouping';
import {
  LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES,
  LIQUIDATION_HEATMAP_MOBILE_AUTO_GROUP_MIN_INTENSITY_USD,
} from '@/utils/constants/chartLiquidationHeatmap';
import { MOBILE_BREAKPOINT_PX } from '@/utils/constants/extended';

describe('useLiquidationHeatmapMobileGrouping', () => {
  const originalInnerWidth = window.innerWidth;

  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes(`max-width: ${MOBILE_BREAKPOINT_PX - 1}px`),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }))
    );
  });

  afterEach(() => {
    window.innerWidth = originalInnerWidth;
    vi.unstubAllGlobals();
  });

  it('raises minIntensityUsd on mobile when overlay is shown', () => {
    window.innerWidth = MOBILE_BREAKPOINT_PX - 1;

    const { result } = renderHook(() =>
      useLiquidationHeatmapMobileGrouping({
        ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES,
        show: true,
        minIntensityUsd: 0,
      })
    );

    expect(result.current.minIntensityUsd).toBe(
      LIQUIDATION_HEATMAP_MOBILE_AUTO_GROUP_MIN_INTENSITY_USD
    );
  });

  it('returns preferences unchanged on desktop viewport', () => {
    window.innerWidth = MOBILE_BREAKPOINT_PX + 100;
    const prefs = {
      ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES,
      show: true,
      minIntensityUsd: 0,
    };

    const { result } = renderHook(() => useLiquidationHeatmapMobileGrouping(prefs));

    expect(result.current).toBe(prefs);
  });
});
