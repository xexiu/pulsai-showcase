// =============================================================================
// Chart Sync: Bar-time helpers (pure UTC ↔ chart-display conversions)
// =============================================================================
//
// SoT: extracted from `chart-sync-helpers.ts` in Phase 2.7.27 (≤400 LOC SRP).
// Consumers import from `@/utils/chart-sync-helpers` which re-exports.
// =============================================================================

import { getTimeframeSeconds } from '@/utils/chart-time';
import { timestampToChartTime } from '@/utils/chart-timestamp';
import { mapUtcBarOpenSecondsForChartDisplay } from '@/utils/chart-timezone';

/**
 * Map a UTC **instant** (e.g. fill `created_at`) to the OHLCV bar **open** (UTC) of the period that contains it.
 *
 * WHY HERE (not `signalTimestampToCandleTime` in markers.ts)?
 * - ML signals use **candle close** timestamps; that helper applies boundary rules (e.g. exact period edge → previous bar).
 * - Demo fills / executions are **wall-clock events** inside a bar; we need the containing bar’s open for the same
 *   x-scale as `applyDashboardCandleDataAndMaybeFit` + `mapOverlayTimesToChartBarScale`.
 *
 * @see signalTimestampToCandleTime — close-time semantics for signal markers/tooltip
 */
export function eventUtcToContainingBarOpenUtc(
  eventUtcSeconds: number,
  timeframe: string | undefined
): number {
  if (timeframe == null || timeframe === '') {
    return eventUtcSeconds;
  }

  const periodSec = getTimeframeSeconds(timeframe);

  if (periodSec <= 0) {
    return eventUtcSeconds;
  }

  return Math.floor(eventUtcSeconds / periodSec) * periodSec;
}

/**
 * Map overlay sample times to the same x-scale as candlestick `setData`.
 *
 * WHY:
 * - **Dashboard:** `applyDashboardCandleDataAndMaybeFit` maps OHLCV bar times before `setData`.
 *   Client indicators (`useIndicators`) must apply the same transform (BB/RSI/MACD).
 * - **Full chart:** `applyFullChartCandleDataAndMaybeFit` maps bar times; BE-derived lines
 *   (`syncRsiMacdBbFull`, period high/low, zones, etc.) must use the same transform or overlays
 *   drift vs candles on intraday TFs (`shouldApplyTimeToTzForTimeframe`).
 *
 * Name is surface-neutral (not "dashboard"): any chart that uses this policy must call here.
 */
export function mapOverlayTimesToChartBarScale<T extends { time: number }>(
  points: T[],
  timezone: string,
  timeframe: string | undefined
): T[] {
  return points.map((p) => ({
    ...p,
    time: mapUtcBarOpenSecondsForChartDisplay(p.time, timezone, timeframe),
  }));
}

/**
 * Full-chart overlay rows aligned to candle `setData` times (same args as BE `candleTimes` + chart TF).
 * Thin wrapper for call-site clarity in `useUnifiedChartSyncIndicatorEffects`; behavior = `mapOverlayTimesToChartBarScale`.
 */
export function getFullChartOverlayTimes<T extends { time: number }>(
  candleTimes: T[],
  chartTimezone: string,
  timeframe: string | undefined
): T[] {
  return mapOverlayTimesToChartBarScale(candleTimes, chartTimezone, timeframe);
}

/**
 * Map a single bar open time (UTC seconds) to the value stored on candlestick series.
 * Used for pivot horizontal line start/end after `calculatePivotPoints` (UTC math unchanged).
 */
export function mapChartBarOpenTimeForDisplay(
  utcSeconds: number,
  chartTimezone: string,
  timeframe: string | undefined
): number {
  return mapUtcBarOpenSecondsForChartDisplay(utcSeconds, chartTimezone, timeframe);
}

/**
 * Bar open times in the same x-scale as candlestick `setData` (after `mapUtcBarOpenSecondsForChartDisplay`).
 * Use with marker times **after** the same `timeToTz`/intraday policy in the markers effect.
 */
export function collectChartScaledCandleBarTimes(
  candleRows: readonly { time: number | string }[],
  chartTimezone: string,
  timeframe: string | undefined
): number[] {
  const out: number[] = [];

  for (const row of candleRows) {
    const utc = timestampToChartTime(row.time);

    if (!Number.isFinite(utc) || utc <= 0) continue;
    out.push(mapChartBarOpenTimeForDisplay(utc, chartTimezone, timeframe));
  }

  return out;
}

/**
 * Align the last overlay bar time with the chart-scaled forming candle so zone boxes
 * (gr_zone / FVG / OB) share the same x-scale as `setData` + `applyLiveCandleUpdate`.
 */
export function syncOverlayTimesWithFormingCandle<T extends { time: number }>(
  overlayTimes: readonly T[],
  formingCandleTime: number | null | undefined
): T[] {
  if (overlayTimes.length === 0) {
    return [];
  }

  if (formingCandleTime == null || !Number.isFinite(formingCandleTime) || formingCandleTime <= 0) {
    return [...overlayTimes];
  }

  const lastIdx = overlayTimes.length - 1;
  const last = overlayTimes[lastIdx];

  if (last == null || formingCandleTime < last.time) {
    return [...overlayTimes];
  }

  const next = overlayTimes.slice();

  next[lastIdx] = { ...last, time: formingCandleTime };

  return next;
}

/**
 * Bar open times strictly between the last API bar and the forming candle.
 * Used when live WS advanced the chart ahead of chart-indicators refetch.
 */
export function enumerateBarOpenTimesAfterLast(
  lastBarTime: number,
  formingBarTime: number,
  timeframe: string | undefined
): number[] {
  if (
    !Number.isFinite(lastBarTime) ||
    !Number.isFinite(formingBarTime) ||
    formingBarTime <= lastBarTime
  ) {
    return [];
  }

  const periodSec = timeframe != null && timeframe.length > 0 ? getTimeframeSeconds(timeframe) : 0;

  if (periodSec <= 0) {
    return [];
  }

  const out: number[] = [];
  let t = lastBarTime + periodSec;

  while (t < formingBarTime) {
    out.push(t);
    t += periodSec;
  }

  return out;
}

/**
 * Ensure the chart-scaled **forming** bar open is included in the bar-time list used with
 * `filterMarkersToLoadedCandleRange` (exact bar-open membership).
 *
 * WHY: historical `data` can lag `update()` by one bar; without the forming time in the set,
 * markers on the live bar would be dropped even though the candle is visible.
 */
export function mergeChartScaledBarTimesWithFormingUtc(
  chartScaledBarTimes: readonly number[],
  formingCandleUtc: number | null | undefined,
  chartTimezone: string,
  timeframe: string | undefined
): number[] {
  const base = [...chartScaledBarTimes];

  if (formingCandleUtc == null || !Number.isFinite(formingCandleUtc) || formingCandleUtc <= 0) {
    return base;
  }

  const formingOnChart = mapChartBarOpenTimeForDisplay(formingCandleUtc, chartTimezone, timeframe);

  if (!Number.isFinite(formingOnChart) || formingOnChart <= 0) {
    return base;
  }

  if (base.includes(formingOnChart)) {
    return base;
  }

  base.push(formingOnChart);

  return base;
}
