/**
 * Opt-in setData / live-candle-merge log emitters.
 *
 * Extracted from ``chart-gap-debug`` (Phase 4b SRP split, 2026-05-29). The
 * analytical primitives (``analyzeBarTimes``, culprit resolver, ``chartGapLog``/
 * ``chartGapWarn``) stay in the host module; this file holds the two heavy
 * emitters that produce the ``VERDICT setData`` / ``VERDICT live-merge*``
 * payloads. No behavior change.
 *
 * @see apps/web/src/utils/chart-gap-debug.ts — host module
 */

import {
  analyzeBarTimes,
  chartGapLog,
  chartGapWarn,
  isChartGapDebugEnabled,
  resolveSetDataGapCulprit,
  resolveSetDataGapHint,
  tailTimes,
  type ChartGapLogSurface,
  type PrepareLwcMetaSample,
} from '@/utils/chart-gap-debug';
import { getTimeframeSeconds } from '@/utils/chart-time';
import {
  mapUtcBarOpenSecondsForChartDisplay,
  shouldApplyTimeToTzForTimeframe,
} from '@/utils/chart-timezone';

export interface LogCandleSetDataGapParams {
  surface: Extract<ChartGapLogSurface, 'dashboard' | 'full'>;
  timeframe: string;
  timezone: string;
  symbol?: string;
  utcBarTimes: readonly number[];
  ohlc?: readonly { open: number; close: number }[];
  prepareMeta?: PrepareLwcMetaSample;
  /** Times actually passed to lightweight-charts after prepare (display scale). */
  lwcBarTimes?: readonly number[];
}

/** Log historical `setData` analysis (UTC source vs display times sent to LWC). */
export function logCandleSetDataGap(params: LogCandleSetDataGapParams): void {
  if (!isChartGapDebugEnabled()) {
    return;
  }

  const periodSec = getTimeframeSeconds(params.timeframe);
  const displayTimes = params.utcBarTimes.map((t) =>
    mapUtcBarOpenSecondsForChartDisplay(t, params.timezone, params.timeframe)
  );
  const utcAnalysis = analyzeBarTimes(params.utcBarTimes, periodSec, params.ohlc);
  const displayAnalysis = analyzeBarTimes(displayTimes, periodSec, params.ohlc);
  const lwcTimes = params.lwcBarTimes ?? [];
  const lwcAnalysis = lwcTimes.length > 0 ? analyzeBarTimes(lwcTimes, periodSec) : undefined;
  const culprit = resolveSetDataGapCulprit(
    utcAnalysis,
    displayAnalysis,
    params.prepareMeta,
    lwcAnalysis
  );

  chartGapWarn('VERDICT setData', {
    culprit,
    beIsCulprit: culprit === 'BE_OHLCV_TIMESTAMP_GAPS',
    feIsCulprit: culprit !== 'BE_OHLCV_TIMESTAMP_GAPS' && culprit !== 'OK_NO_GAP_IN_DATA',
    surface: params.surface,
    symbol: params.symbol,
    timeframe: params.timeframe,
    timezone: params.timezone,
    legacyTimeToTz: shouldApplyTimeToTzForTimeframe(params.timeframe),
    periodSec,
    utcTimeGapCount: utcAnalysis.timeGapCount,
    displayTimeGapCount: displayAnalysis.timeGapCount,
    lwcTimeGapCount: lwcAnalysis?.timeGapCount ?? 0,
    utcGapSamples: utcAnalysis.timeGaps,
    displayGapSamples: displayAnalysis.timeGaps,
    lwcGapSamples: lwcAnalysis?.timeGaps ?? [],
    prepareMeta: params.prepareMeta,
    hint: resolveSetDataGapHint(culprit),
  });

  chartGapLog('setData', {
    surface: params.surface,
    symbol: params.symbol,
    timeframe: params.timeframe,
    timezone: params.timezone,
    legacyTimeToTz: shouldApplyTimeToTzForTimeframe(params.timeframe),
    periodSec,
    culprit,
    tailUtc: tailTimes(params.utcBarTimes),
    tailDisplay: tailTimes(displayTimes),
    utc: utcAnalysis,
    display: displayAnalysis,
    priceDiscontinuityCount: utcAnalysis.priceDiscontinuityCount,
    prepareMeta: params.prepareMeta,
  });
}

/** Log live candle merge (historical last bar vs WS bar, normalization, chart update time). */
