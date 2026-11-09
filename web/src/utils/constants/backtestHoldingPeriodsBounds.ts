/**
 * Timeframe-aware max holding periods — mirrors BE resolve_backtest_holding_periods_max.
 *
 * @see apps/api/src/shared/backtest_holding_periods_bounds.py
 */

import { CANDLES_PER_DAY, type ChartTimeframe } from '@/utils/chart-time';

/** Minimum candles (BE ge=1). */
export const BACKTEST_HOLDING_PERIODS_MIN = 1;

/** HTF cap (1h, 4h, 1d, unknown). */
export const BACKTEST_HOLDING_PERIODS_MAX_HTF = 100;

/** Hard ceiling for intraday formula. */
const BACKTEST_HOLDING_PERIODS_ABSOLUTE_CEILING = 1000;

/** Calendar days in intraday max-hold formula. */
const BACKTEST_MAX_HOLD_CALENDAR_DAYS = 14;

const BACKTEST_HOLDING_PERIODS_INTRADAY_TIMEFRAMES = new Set<string>(['5m', '15m', '30m']);

/**
 * Max candles allowed for holding on this timeframe.
 */
export function resolveBacktestHoldingPeriodsMax(timeframe: string): number {
  const normalized = timeframe.trim().toLowerCase();

  if (!BACKTEST_HOLDING_PERIODS_INTRADAY_TIMEFRAMES.has(normalized)) {
    return BACKTEST_HOLDING_PERIODS_MAX_HTF;
  }

  const candlesPerDay = CANDLES_PER_DAY[normalized as ChartTimeframe] ?? CANDLES_PER_DAY['1h'];
  const calendarCap = candlesPerDay * BACKTEST_MAX_HOLD_CALENDAR_DAYS;

  return Math.min(BACKTEST_HOLDING_PERIODS_ABSOLUTE_CEILING, calendarCap);
}
