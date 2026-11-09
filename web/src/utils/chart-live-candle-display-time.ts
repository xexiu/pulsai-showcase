/**
 * Resolve live candle `update()` time on the same x-scale as `setData` (display / timeToTz).
 *
 * WHY: `data[]` can lag the series after `update()` or during TanStack refetch; merging against
 * stale UTC `data[last]` can target a bar behind the chart and later ticks can insert bars with
 * holes. Anchor on the last display time applied to the series when available.
 */

import { getTimeframeSeconds } from '@/utils/chart-time';
import { mapUtcBarOpenSecondsForChartDisplay } from '@/utils/chart-timezone';

export interface ResolveLiveCandleDisplayTimeParams {
  dataLastUtc: number;
  liveUtc: number;
  /** Last bar time actually sent to LWC (display scale); null until first setData/update. */
  chartLastDisplayTime: number | null;
  timezone: string;
  timeframe: string;
}

interface ResolveLiveCandleNormalizedUtcParams {
  liveUtc: number;
  dataLastUtc: number;
  liveDisplay: number;
  displayTime: number;
  periodSec: number;
}

/** UTC open used for OHLC merge before display mapping (after gap cap). */
function resolveLiveCandleNormalizedUtc(p: ResolveLiveCandleNormalizedUtcParams): number {
  if (p.liveUtc > p.dataLastUtc && p.displayTime === p.liveDisplay) {
    return p.liveUtc;
  }
  if (p.liveUtc <= p.dataLastUtc + p.periodSec) {
    return p.liveUtc;
  }

  return p.dataLastUtc + p.periodSec;
}

export interface ResolveLiveCandleDisplayTimeResult {
  /** Time passed to `series.update()` (display scale). */
  displayTime: number;
  /** UTC open used for OHLC merge before display mapping (after gap cap). */
  normalizedUtc: number;
  dataLastDisplay: number;
  liveDisplay: number;
  anchorDisplay: number;
  /** True when live was >1 period ahead of anchor and time was capped to anchor+period. */
  cappedAhead: boolean;
}

/**
 * Map display time back to UTC bar open for the same wall-clock bar (inverse of mapUtc display).
 * Used only for logging; merge uses display time on the series.
 */
export function resolveLiveCandleDisplayTime(
  params: ResolveLiveCandleDisplayTimeParams
): ResolveLiveCandleDisplayTimeResult | null {
  const { dataLastUtc, liveUtc, chartLastDisplayTime, timezone, timeframe } = params;
  const periodSec = getTimeframeSeconds(timeframe);

  if (periodSec <= 0 || liveUtc < dataLastUtc) {
    return null;
  }

  const dataLastDisplay = mapUtcBarOpenSecondsForChartDisplay(dataLastUtc, timezone, timeframe);
  const liveDisplay = mapUtcBarOpenSecondsForChartDisplay(liveUtc, timezone, timeframe);
  const chartLast = chartLastDisplayTime ?? dataLastDisplay;
  // After series clear / placeholder, ref can point past what setData wrote — anchoring on it
  // paints a lone bar with a horizontal hole (DEBUG_CHART_GAP: anchor >> series end).
  const anchorDisplay =
    chartLast > dataLastDisplay + periodSec
      ? dataLastDisplay
      : Math.max(chartLast, dataLastDisplay);

  let displayTime = liveUtc === dataLastUtc ? dataLastDisplay : liveDisplay;
  let cappedAhead = false;

  if (displayTime > anchorDisplay + periodSec) {
    const periodsAhead = Math.round((liveUtc - dataLastUtc) / periodSec);

    // REST 1–2 bars behind WS: paint forming bar at liveDisplay; overlays extend via
    // extendOverlayLineDataToFormingDisplay. Only cap when REST is 3+ bars stale.
    if (periodsAhead >= 3) {
      displayTime = anchorDisplay + periodSec;
      cappedAhead = true;
    }
  }

  if (displayTime < anchorDisplay) {
    displayTime = anchorDisplay;
  }

  const normalizedUtc = resolveLiveCandleNormalizedUtc({
    liveUtc,
    dataLastUtc,
    liveDisplay,
    displayTime,
    periodSec,
  });

  return {
    displayTime,
    normalizedUtc,
    dataLastDisplay,
    liveDisplay,
    anchorDisplay,
    cappedAhead,
  };
}
