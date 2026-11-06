/**
 * Opt-in live-candle investigation traces (console).
 * Enable: `?debugChartGap=1` or `localStorage DEBUG_CHART_GAP=1`.
 */

import { CHART_GAP_DEBUG_LOG_PREFIX } from '@/config/chart-constants';
import { isChartGapDebugEnabled } from '@/utils/chart-gap-debug';

let mergeSeq = 0;

/** Monotonic id per `series.update()` attempt when debug is on. */
export function nextChartLiveMergeSeq(): number {
  mergeSeq += 1;

  return mergeSeq;
}

export function chartLiveTrace(
  event: string,
  payload: Record<string, unknown>,
  level: 'log' | 'warn' = 'log'
): void {
  if (!isChartGapDebugEnabled()) {
    return;
  }

  const line = `${CHART_GAP_DEBUG_LOG_PREFIX} ${event}`;
  const body = { t: Date.now(), ...payload };

  if (level === 'warn') {
    console.warn(line, body);
  } else {
    console.info(line, body);
  }
}
