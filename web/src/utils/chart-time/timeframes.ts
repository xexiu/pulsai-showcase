import { buildChartTimeframeMs } from '@pulsai/shared';

import type { ChartTimeframe } from '@/utils/chart-time/types';

/**
 * Timeframe to milliseconds mapping.
 *
 * Registry keys mirror BE `TIMEFRAME_REGISTRY`; chart-only keys (3m, 2h, 6h) extend
 * pivot/countdown math without duplicating product durations.
 */
export const TIMEFRAME_MS: Record<ChartTimeframe, number> = buildChartTimeframeMs() as Record<
  ChartTimeframe,
  number
>;

/**
 * SoT for timeframe → period length in seconds. Derived once from TIMEFRAME_MS at module load.
 * Use this (or getTimeframeSeconds for arbitrary string) instead of Math.floor(periodMs / 1000) anywhere.
 */
export const TIMEFRAME_SEC: Record<ChartTimeframe, number> = Object.fromEntries(
  (Object.entries(TIMEFRAME_MS) as [ChartTimeframe, number][]).map(([k, v]) => [
    k,
    Math.floor(v / 1000),
  ])
) as Record<ChartTimeframe, number>;

/**
 * Number of candles per day for each timeframe.
 *
 * WHY THIS MAPPING?
 * - Pivot points should represent the previous day's range
 * - Different timeframes have different candle counts per day
 * - This ensures consistent pivot levels across all timeframes
 *
 * CALCULATION: 24 hours / timeframe hours
 * - 1m = 60 * 24 = 1440 candles/day
 * - 15m = 4 * 24 = 96 candles/day
 * - 1h = 24 candles/day
 * - 4h = 6 candles/day
 *
 * SPECIAL CASES:
 * - 1d: Uses 1 candle (daily pivots from previous day). R2/R1/PP/S1/S2 are then all within
 *   that single day's range, so they appear "tight" on the chart — this is correct.
 * - 1w: Uses 1 candle (weekly pivots - different methodology)
 */
export const CANDLES_PER_DAY: Record<ChartTimeframe, number> = {
  '1m': 1440, // 60 * 24
  '3m': 480, // 20 * 24
  '5m': 288, // 12 * 24
  '15m': 96, // 4 * 24
  '30m': 48, // 2 * 24
  '1h': 24, // 1 * 24
  '2h': 12, // 0.5 * 24
  '4h': 6, // 0.25 * 24
  '6h': 4, // 24 / 6
  '8h': 3, // 24 / 8
  '12h': 2, // 24 / 12
  '1d': 1, // Daily pivots from previous day (tight clustering is expected)
  '3d': 1, // Multi-day bar: use prior completed calendar day for daily pivots
  '1w': 5, // Weekly: use 5 trading days
};

/**
 * Get the pivot period (number of candles) for a given timeframe.
 *
 * WHY THIS FUNCTION?
 * - Pivot points should always represent "yesterday's range"
 * - A 15m trader and 4h trader should see the SAME pivot levels
 * - This function returns how many candles equal 1 day
 *
 * @param timeframe - Chart timeframe string
 * @returns Number of candles to use for pivot calculation
 *
 * @example
 * getPivotPeriodForTimeframe('15m')  // 96 (96 fifteen-minute candles = 1 day)
 * getPivotPeriodForTimeframe('4h')   // 6  (6 four-hour candles = 1 day)
 * getPivotPeriodForTimeframe('1h')   // 24 (24 hourly candles = 1 day)
 */
export function getPivotPeriodForTimeframe(timeframe: string): number {
  const period = CANDLES_PER_DAY[timeframe as ChartTimeframe];

  // Default to 24 (hourly) if timeframe not found
  if (!period) {
    return 24;
  }

  return period;
}

/** Seconds in one day (UTC). Used to anchor pivots to previous completed day (TradingView parity). */
const SECONDS_PER_DAY = 86400;

const DAYS_PER_WEEK = 7;

/** Seconds in one week. Used for weekly pivot timeframe. */
const SECONDS_PER_WEEK = SECONDS_PER_DAY * DAYS_PER_WEEK;

/**
 * Monday weekly candle anchor (seconds since Unix epoch).
 *
 * Mirrors BE ``WEEKLY_CANDLE_OPEN_ANCHOR_MS`` (4 days). The epoch (1970-01-01) is Thursday;
 * naive ``(utc // week) * week`` floors to Thursday and breaks 1w live merge + REST tail.
 *
 * @see apps/api/src/shared/constants/timeframes.py
 * @see apps/api/tests/shared/constants/test_timeframes.py::TestWeeklyMondayAlignment
 */
/** Monday 00:00 UTC weekly open (matches BE `period_start_ms` for `1w`). */
const WEEKLY_CANDLE_OPEN_ANCHOR_SEC = 4 * SECONDS_PER_DAY;

/**
 * Binance native ``3d`` open anchor (matches BE ``THREE_DAY_BINANCE_CANDLE_OPEN_ANCHOR_MS``).
 * Pure epoch floor is always off by one calendar day vs live Binance klines.
 */
const THREE_DAY_BINANCE_CANDLE_OPEN_ANCHOR_SEC = SECONDS_PER_DAY;

/**
 * Floor UTC seconds to the exchange candle open for the timeframe bucket.
 *
 * EPOCH-aligned TFs (5m–1d): anchor 0. ``3d``: Binance epoch+1d. ``1w``: Monday 00:00 UTC.
 */
export function floorUtcCandlePeriodOpenSeconds(timeframe: string, utcSeconds: number): number {
  const periodSec = TIMEFRAME_SEC[timeframe as ChartTimeframe];

  if (periodSec == null || periodSec <= 0 || !Number.isFinite(utcSeconds)) {
    return utcSeconds;
  }

  let anchorSec = 0;

  if (timeframe === '1w') {
    anchorSec = WEEKLY_CANDLE_OPEN_ANCHOR_SEC;
  } else if (timeframe === '3d') {
    anchorSec = THREE_DAY_BINANCE_CANDLE_OPEN_ANCHOR_SEC;
  }

  return Math.floor((utcSeconds - anchorSec) / periodSec) * periodSec + anchorSec;
}

/**
 * Get pivot period duration in seconds for timeframe (TradingView parity).
 *
 * Daily pivots = previous day's H/L/C; weekly = previous week's.
 * Used to select candles in the previous completed period, not "last N bars".
 *
 * @param timeframe - Chart timeframe string
 * @returns Period length in seconds (86400 for daily, 604800 for 1w)
 */
export function getPivotPeriodSecondsForTimeframe(timeframe: string): number {
  if (timeframe === '1w') {
    return SECONDS_PER_WEEK;
  }

  return SECONDS_PER_DAY;
}
