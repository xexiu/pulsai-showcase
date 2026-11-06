import { TIMEFRAME_MS, TIMEFRAME_SEC } from '@/utils/chart-time/timeframes';
import type { ChangeResult, ChartTimeframe } from '@/utils/chart-time/types';

/**
 * Format remaining time as HH:MM:SS or MM:SS string.
 *
 * @param remainingMs - Remaining time in milliseconds
 * @returns Formatted time string
 */
function formatRemainingTime(remainingMs: number): string {
  const hours = Math.floor(remainingMs / (60 * 60 * 1000));
  const minutes = Math.floor((remainingMs % (60 * 60 * 1000)) / (60 * 1000));
  const seconds = Math.floor((remainingMs % (60 * 1000)) / 1000);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }

  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Calculate countdown to next candle close.
 *
 * WHY THIS FUNCTION?
 * - Traders need to know when current candle closes
 * - Important for entry/exit timing decisions
 * - Updates every second in ChartLegend
 *
 * @param timeframe - Chart timeframe (e.g., "1h", "4h")
 * @param now - Current timestamp (default: Date.now(), injectable for testing)
 * @returns Formatted countdown string (MM:SS or HH:MM:SS)
 *
 * @example
 * calculateCountdown('1h')    // "45:23" (45 min 23 sec until next hour)
 * calculateCountdown('4h')    // "2:45:23" (2h 45m 23s until next 4h candle)
 */
export function calculateCountdown(timeframe: string, now: number = Date.now()): string {
  const intervalMs = TIMEFRAME_MS[timeframe as ChartTimeframe];

  if (!intervalMs) {
    return '--:--';
  }

  const nextCandleTime = Math.ceil(now / intervalMs) * intervalMs;
  const remaining = nextCandleTime - now;

  return formatRemainingTime(remaining);
}

/**
 * Calculate percentage change between two prices.
 *
 * WHY RETURN OBJECT?
 * - `value`: Always positive for display formatting
 * - `isPositive`: For color coding (green/red)
 * - Avoids -0.00% display issues
 *
 * @param current - Current price
 * @param previous - Previous price (baseline)
 * @returns Object with absolute change value and direction (SoT for legend display).
 *
 * @example
 * calculatePriceChange(105, 100)  // { value: 5, isPositive: true }
 * calculatePriceChange(95, 100)   // { value: 5, isPositive: false }
 */
export function calculatePriceChange(current: number, previous: number): ChangeResult {
  if (previous === 0) {
    return { value: 0, isPositive: true };
  }

  const change = ((current - previous) / previous) * 100;

  return {
    value: Math.abs(change),
    isPositive: change >= 0,
  };
}

/**
 * Get the next candle close timestamp.
 *
 * @param timeframe - Chart timeframe
 * @param now - Current timestamp (default: Date.now())
 * @returns Unix timestamp of next candle close, or null if invalid timeframe
 */
export function getNextCandleClose(timeframe: string, now: number = Date.now()): number | null {
  const intervalMs = TIMEFRAME_MS[timeframe as ChartTimeframe];

  if (!intervalMs) {
    return null;
  }

  return Math.ceil(now / intervalMs) * intervalMs;
}

/**
 * Get milliseconds for a timeframe.
 *
 * @param timeframe - Chart timeframe string
 * @returns Milliseconds, or null if invalid timeframe
 */
export function getTimeframeMs(timeframe: string): number | null {
  return TIMEFRAME_MS[timeframe as ChartTimeframe] ?? null;
}

/**
 * Lookup period in seconds for arbitrary timeframe string. Uses TIMEFRAME_SEC (SoT).
 *
 * @param timeframe - Chart timeframe string (e.g. '1h')
 * @returns Period in seconds, or 0 if invalid/unknown timeframe
 */
export function getTimeframeSeconds(timeframe: string): number {
  return TIMEFRAME_SEC[timeframe as ChartTimeframe] ?? 0;
}

/**
 * True if current time (UTC) is within the forming candle's period [open, close).
 * Used to show forming tooltip and to ensure we only treat a bar as forming when now is in range.
 */
