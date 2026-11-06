/**
 * Opt-in chart candle gap investigation (time-axis holes, live merge, UTC vs display).
 *
 * Opt-in gap diagnostics — logs to the browser console when enabled.
 * Enable: localStorage DEBUG_CHART_GAP=1 or ?debugChartGap=1
 *
 * Phase 4b SRP split (2026-05-29): the two heaviest emitters (``logCandleSetDataGap``,
 * ``logLiveCandleMerge``) live in :mod:`./chart-gap-debug-emitters` and are
 * re-exported below to keep the public API stable for callers.
 *
 * @see apps/web/src/config/chart-constants.ts — CHART_GAP_DEBUG_LOG_PREFIX
 */

import { CHART_GAP_DEBUG_LOG_PREFIX } from '@/config/chart-constants';
import { getTimeframeSeconds } from '@/utils/chart-time';

export const DEBUG_CHART_GAP_STORAGE_KEY = 'DEBUG_CHART_GAP';

const MAX_GAP_SAMPLES = 8;
const MAX_TAIL_BARS = 6;

const TIME_GAP_EPSILON_SEC = 2;

const PRICE_DISCONTINUITY_MIN_PCT = 0.15;

export type ChartGapLogSurface = 'dashboard' | 'full' | 'live';

interface BarTimeGapSample {
  index: number;
  prevTime: number;
  time: number;
  deltaSec: number;
  expectedDeltaSec: number;
}

interface PriceDiscontinuitySample {
  index: number;
  prevClose: number;
  open: number;
  pctMove: number;
}

export interface AnalyzeBarTimesResult {
  barCount: number;
  periodSec: number;
  timeGapCount: number;
  timeGaps: BarTimeGapSample[];
  duplicateTimeCount: number;
  nonAscendingCount: number;
  priceDiscontinuityCount: number;
  priceDiscontinuities: PriceDiscontinuitySample[];
}

function readDebugFlag(storageKey: string): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    return window.localStorage.getItem(storageKey) === '1';
  } catch {
    return false;
  }
}

export function isChartGapDebugEnabled(): boolean {
  if (readDebugFlag(DEBUG_CHART_GAP_STORAGE_KEY)) {
    return true;
  }

  if (typeof window === 'undefined') {
    return false;
  }

  try {
    return new URLSearchParams(window.location.search).get('debugChartGap') === '1';
  } catch {
    return false;
  }
}

/** Opt-in gap diagnostics — `console.info`. */
export function chartGapLog(label: string, payload?: Record<string, unknown>): void {
  if (!isChartGapDebugEnabled()) {
    return;
  }

  console.info(`${CHART_GAP_DEBUG_LOG_PREFIX} ${label}`, {
    t: Date.now(),
    ...payload,
  });
}

/** Opt-in gap verdicts — `console.warn`. */
export function chartGapWarn(label: string, payload: Record<string, unknown>): void {
  if (!isChartGapDebugEnabled()) {
    return;
  }

  console.warn(`${CHART_GAP_DEBUG_LOG_PREFIX} ${label}`, {
    t: Date.now(),
    ...payload,
  });
}

export type ChartGapCulprit =
  | 'BE_OHLCV_TIMESTAMP_GAPS'
  | 'FE_DISPLAY_MAPPING_GAPS'
  | 'FE_LWC_SERIES_GAPS'
  | 'FE_PREP_DEDUPED_BARS'
  | 'FE_PREP_DROPPED_BARS'
  | 'FE_LIVE_MERGE_SUSPECT'
  | 'OK_NO_GAP_IN_DATA';

export function resolveSetDataGapHint(culprit: ChartGapCulprit): string {
  if (culprit === 'BE_OHLCV_TIMESTAMP_GAPS') {
    return 'Backend returned holey timestamps — run apps/api/scripts/investigate_chart_gaps.py';
  }

  if (culprit === 'FE_DISPLAY_MAPPING_GAPS') {
    return 'timeToTz/Madrid created display holes though UTC is fine';
  }

  if (culprit === 'FE_PREP_DEDUPED_BARS') {
    return 'prepareLwcCandleSeriesData collapsed duplicate display times';
  }

  if (culprit === 'FE_LWC_SERIES_GAPS') {
    return 'Bars sent to lightweight-charts have display-time holes (often after prepare/dedupe)';
  }

  if (culprit === 'FE_PREP_DROPPED_BARS') {
    return 'prepareLwcCandleSeriesData dropped invalid OHLC rows — chart can show holes';
  }

  return 'Historical setData is contiguous; remaining holes = live merge or zoom';
}

export interface PrepareLwcMetaSample {
  droppedInvalidCount: number;
  duplicateTimeCount: number;
  lwcBarCount: number;
}

export function resolveSetDataGapCulprit(
  utcAnalysis: AnalyzeBarTimesResult,
  displayAnalysis: AnalyzeBarTimesResult,
  prepareMeta?: PrepareLwcMetaSample,
  lwcAnalysis?: AnalyzeBarTimesResult
): ChartGapCulprit {
  if (utcAnalysis.timeGapCount > 0) {
    return 'BE_OHLCV_TIMESTAMP_GAPS';
  }

  if (displayAnalysis.timeGapCount > 0) {
    return 'FE_DISPLAY_MAPPING_GAPS';
  }

  if (lwcAnalysis != null && lwcAnalysis.timeGapCount > 0) {
    return 'FE_LWC_SERIES_GAPS';
  }

  if (prepareMeta != null && prepareMeta.duplicateTimeCount > 0) {
    return 'FE_PREP_DEDUPED_BARS';
  }

  if (prepareMeta != null && prepareMeta.droppedInvalidCount > 0) {
    return 'FE_PREP_DROPPED_BARS';
  }

  return 'OK_NO_GAP_IN_DATA';
}

export interface LogOhlcvApiGapParams {
  symbol: string;
  timeframe: string;
  consumer: string;
  isPlaceholderData: boolean;
  candleCount: number;
  utcBarTimes: readonly number[];
}

/** Log TanStack OHLCV payload as received from API (before chart sync). */
export function logOhlcvApiGapCheck(params: LogOhlcvApiGapParams): void {
  if (!isChartGapDebugEnabled()) {
    return;
  }

  const periodSec = getTimeframeSeconds(params.timeframe);
  const analysis = analyzeBarTimes(params.utcBarTimes, periodSec);
  const culprit =
    analysis.timeGapCount > 0 ? 'BE_OHLCV_TIMESTAMP_GAPS' : ('OK_NO_GAP_IN_DATA' as const);

  chartGapWarn('VERDICT ohlcv-api', {
    culprit,
    symbol: params.symbol,
    timeframe: params.timeframe,
    consumer: params.consumer,
    isPlaceholderData: params.isPlaceholderData,
    candleCount: params.candleCount,
    periodSec,
    timeGapCount: analysis.timeGapCount,
    timeGaps: analysis.timeGaps,
    duplicateUtcTimes: analysis.duplicateTimeCount,
    beIsCulprit: analysis.timeGapCount > 0,
    hint:
      analysis.timeGapCount > 0
        ? 'Gaps in API JSON timestamps — fix Redis/Postgres/ohlcv_service, not LWC'
        : 'API series is contiguous; holes on chart are FE (display, dedupe, or live merge)',
  });

  chartGapLog('ohlcv-api', {
    symbol: params.symbol,
    timeframe: params.timeframe,
    consumer: params.consumer,
    isPlaceholderData: params.isPlaceholderData,
    analysis,
    tailUtc: tailTimes(params.utcBarTimes),
  });
}

function collectPriceDiscontinuities(
  bars: readonly { open: number; close: number }[]
): Pick<AnalyzeBarTimesResult, 'priceDiscontinuityCount' | 'priceDiscontinuities'> {
  const priceDiscontinuities: PriceDiscontinuitySample[] = [];

  for (let i = 1; i < bars.length; i += 1) {
    const prev = bars[i - 1];
    const cur = bars[i];

    if (prev == null || cur == null) continue;

    const prevClose = prev.close;
    const denom = Math.abs(prevClose) || 1;
    const pctMove = (Math.abs(cur.open - prevClose) / denom) * 100;

    if (pctMove < PRICE_DISCONTINUITY_MIN_PCT) continue;

    priceDiscontinuities.push({
      index: i,
      prevClose,
      open: cur.open,
      pctMove: Math.round(pctMove * 100) / 100,
    });
  }

  const sorted = [...priceDiscontinuities].sort((a, b) => b.pctMove - a.pctMove);

  return {
    priceDiscontinuityCount: priceDiscontinuities.length,
    priceDiscontinuities: sorted.slice(0, MAX_GAP_SAMPLES),
  };
}

/**
 * Detect non-consecutive bar opens (LWC leaves horizontal space) and large open-vs-prev-close jumps.
 */
export function analyzeBarTimes(
  times: readonly number[],
  periodSec: number,
  ohlc?: readonly { open: number; close: number }[]
): AnalyzeBarTimesResult {
  const validTimes = times.filter((t) => Number.isFinite(t) && t > 0);
  const timeGaps: BarTimeGapSample[] = [];
  let duplicateTimeCount = 0;
  let nonAscendingCount = 0;

  for (let i = 1; i < validTimes.length; i += 1) {
    const prevTime = validTimes[i - 1]!;
    const time = validTimes[i]!;
    const deltaSec = time - prevTime;

    if (deltaSec <= 0) {
      if (deltaSec === 0) {
        duplicateTimeCount += 1;
      } else {
        nonAscendingCount += 1;
      }
      continue;
    }

    if (periodSec > 0 && deltaSec > periodSec + TIME_GAP_EPSILON_SEC) {
      timeGaps.push({
        index: i,
        prevTime,
        time,
        deltaSec,
        expectedDeltaSec: periodSec,
      });
    }
  }

  const pricePart =
    ohlc != null && ohlc.length === validTimes.length
      ? collectPriceDiscontinuities(ohlc)
      : { priceDiscontinuityCount: 0, priceDiscontinuities: [] as PriceDiscontinuitySample[] };

  return {
    barCount: validTimes.length,
    periodSec,
    timeGapCount: timeGaps.length,
    timeGaps: timeGaps.slice(0, MAX_GAP_SAMPLES),
    duplicateTimeCount,
    nonAscendingCount,
    ...pricePart,
  };
}

export function tailTimes(times: readonly number[]): number[] {
  if (times.length <= MAX_TAIL_BARS) {
    return [...times];
  }

  return times.slice(-MAX_TAIL_BARS);
}

// `logCandleSetDataGap` and `logLiveCandleMerge` live in the sibling emitter
// module (Phase 4b SRP split). Re-exported here so callers that import from
// `@/utils/chart-gap-debug` keep the same surface.
export { logCandleSetDataGap } from '@/utils/chart-gap-debug-emitters';
