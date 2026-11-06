// =============================================================================
// Chart Time Utilities - Countdown and timeframe calculations
// =============================================================================
//
// SoT: time = timeframes, countdown, limits (legend, alerts, fetch limits).
// For normalising external timestamps to chart seconds, use chart-timestamp.
//
// WHY SEPARATE FILE?
// - TESTABLE: Pure functions for countdown logic
// - REUSABLE: Used by ChartLegend, notifications, alerts
// - SINGLE SOURCE: Timeframe definitions in one place
// =============================================================================

export {
  calculateCountdown,
  calculatePriceChange,
  getNextCandleClose,
  getTimeframeMs,
  getTimeframeSeconds,
} from '@/utils/chart-time/countdown';
export { getDivergencePivotLookbackBars } from '@/utils/chart-time/divergence-params';
export { getSignalLimitForTimeframe, getSignalLimitsForTier } from '@/utils/chart-time/limits';
export {
  CANDLES_PER_DAY,
  floorUtcCandlePeriodOpenSeconds,
  getPivotPeriodForTimeframe,
  getPivotPeriodSecondsForTimeframe,
  TIMEFRAME_MS,
  TIMEFRAME_SEC,
} from '@/utils/chart-time/timeframes';
export type { ChartTimeframe } from '@/utils/chart-time/types';
