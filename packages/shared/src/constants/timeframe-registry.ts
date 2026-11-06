// =============================================================================
// Timeframe registry — mirrors BE TIMEFRAME_REGISTRY (SoT)
// =============================================================================
//
// Keep milliseconds in sync with:
//   apps/api/src/shared/constants/timeframes.py → TIMEFRAME_REGISTRY
//
// Product deployment defaults mirror:
//   DEFAULT_SUPPORTED_TIMEFRAME_VALUES in the same Python module.

/** BE registry keys → candle duration in milliseconds. */
export const TIMEFRAME_REGISTRY_MS = {
  '1m': 60 * 1000,
  '5m': 5 * 60 * 1000,
  '15m': 15 * 60 * 1000,
  '30m': 30 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '2h': 2 * 60 * 60 * 1000,
  '4h': 4 * 60 * 60 * 1000,
  '6h': 6 * 60 * 60 * 1000,
  '8h': 8 * 60 * 60 * 1000,
  '12h': 12 * 60 * 60 * 1000,
  '1d': 24 * 60 * 60 * 1000,
  '3d': 3 * 24 * 60 * 60 * 1000,
  '1w': 7 * 24 * 60 * 60 * 1000,
} as const;

export type RegistryTimeframe = keyof typeof TIMEFRAME_REGISTRY_MS;

/**
 * Chart-helper durations not in the BE product registry.
 * Used only for pivot/countdown math — not exposed as trading timeframes.
 *
 * `2h` and `6h` USED to live here. They were promoted into the BE registry on 2026-08-12 as real
 * training-band members (LTF 5m..2h, HTF 4h..1d) — trainable, default-supported, and served by
 * GET /config/public — so leaving them here told the frontend that two genuine trading timeframes
 * were chart decoration. Moved up, not duplicated: a timeframe belongs to exactly one of these.
 */
export const CHART_ONLY_TIMEFRAME_MS = {
  '3m': 3 * 60 * 1000,
} as const;

export type ChartOnlyTimeframe = keyof typeof CHART_ONLY_TIMEFRAME_MS;

/** Default deployment-supported timeframes (BE `DEFAULT_SUPPORTED_TIMEFRAME_VALUES`). */
export const DEFAULT_SUPPORTED_TIMEFRAMES = [
  '5m',
  '15m',
  '30m',
  '1h',
  '2h',
  '4h',
  '6h',
  '8h',
  '12h',
  '1d',
  '3d',
  '1w',
] as const satisfies readonly RegistryTimeframe[];

export const TIMEFRAME_LABELS: Record<RegistryTimeframe, string> = {
  '1m': '1 Minute',
  '5m': '5 Minutes',
  '15m': '15 Minutes',
  '30m': '30 Minutes',
  '1h': '1 Hour',
  '2h': '2 Hours',
  '4h': '4 Hours',
  '6h': '6 Hours',
  '8h': '8 Hours',
  '12h': '12 Hours',
  '1d': '1 Day',
  '3d': '3 Days',
  '1w': '1 Week',
};

export function registryTimeframeToMinutes(tf: RegistryTimeframe): number {
  return TIMEFRAME_REGISTRY_MS[tf] / (60 * 1000);
}

/** Merge BE registry ms with chart-only extensions for chart utilities. */
export function buildChartTimeframeMs(): Record<RegistryTimeframe | ChartOnlyTimeframe, number> {
  return { ...TIMEFRAME_REGISTRY_MS, ...CHART_ONLY_TIMEFRAME_MS };
}
