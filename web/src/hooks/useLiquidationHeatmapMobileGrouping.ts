'use client';

import { useSyncExternalStore } from 'react';

import { MOBILE_BREAKPOINT_PX } from '@/utils/constants';
import {
  LIQUIDATION_HEATMAP_MOBILE_AUTO_GROUP_MIN_INTENSITY_USD,
  type LiquidationHeatmapOverlayPreferences,
} from '@/utils/constants/chartLiquidationHeatmap';

function subscribeMobileViewport(onStoreChange: () => void): () => void {
  if (typeof window === 'undefined') {
    return () => undefined;
  }

  const media = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT_PX - 1}px)`);
  const handler = (): void => onStoreChange();

  media.addEventListener('change', handler);

  return () => media.removeEventListener('change', handler);
}

function getIsMobileViewportSnapshot(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  return window.innerWidth < MOBILE_BREAKPOINT_PX;
}

/** Apply mobile auto-group floor to min intensity without mutating stored prefs. */
export function useLiquidationHeatmapMobileGrouping(
  preferences: LiquidationHeatmapOverlayPreferences
): LiquidationHeatmapOverlayPreferences {
  const isMobile = useSyncExternalStore(
    subscribeMobileViewport,
    getIsMobileViewportSnapshot,
    () => false
  );

  if (!isMobile || !preferences.show) {
    return preferences;
  }

  const minIntensityUsd = Math.max(
    preferences.minIntensityUsd,
    LIQUIDATION_HEATMAP_MOBILE_AUTO_GROUP_MIN_INTENSITY_USD
  );

  if (minIntensityUsd === preferences.minIntensityUsd) {
    return preferences;
  }

  return { ...preferences, minIntensityUsd };
}
