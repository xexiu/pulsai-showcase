/**
 * SoT: timestamp = normalising external timestamps to chart time (Unix seconds).
 * For timeframes, countdown, limits use chart-time.
 *
 * Any timestamp (backend ms, sec, or ISO string) → chart seconds. Use for candles,
 * volume, and signals. Used by parseBackendCandles, chartIndicatorsToChartData,
 * chart-converters, and chart-tooltip-signals / chart-tooltip-state.
 *
 * @see apps/web/src/utils/ohlcv-api.ts
 * @see apps/web/src/utils/full-chart.ts
 */

/** Values >= this are treated as milliseconds; below as seconds. Backend sends ms. */
export const CHART_TIMESTAMP_MS_THRESHOLD = 1e12;

/**
 * Convert backend timestamp to chart time (Unix seconds).
 *
 * @param ts - Backend value: number (ms or sec) or ISO string.
 * @returns Unix seconds for lightweight-charts; NaN for invalid input (callers filter out).
 *
 * @example
 * timestampToChartTime(1710512100000) // ms → 1710512100
 * timestampToChartTime(1710512100)   // sec → 1710512100
 * timestampToChartTime('2024-03-16T15:15:00.000Z') // → 1710512100
 * timestampToChartTime('bad') // → NaN
 */
export function timestampToChartTime(ts: unknown): number {
  if (typeof ts === 'number') {
    if (!Number.isFinite(ts)) {
      return Number.NaN;
    }
    if (ts >= CHART_TIMESTAMP_MS_THRESHOLD) {
      return Math.floor(ts / 1000);
    }

    return Math.floor(ts);
  }

  if (typeof ts === 'string') {
    const ms = Date.parse(ts);

    return Number.isFinite(ms) ? Math.floor(ms / 1000) : Number.NaN;
  }

  return Number.NaN;
}
