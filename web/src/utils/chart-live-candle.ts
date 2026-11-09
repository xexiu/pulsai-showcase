/**
 * Live candle update logic for lightweight-charts (single place for dashboard + full-chart).
 *
 * WHY SEPARATE? useUnifiedChartSync is the single sync implementation; it needs
 * applyLiveCandleUpdate without importing from useChartDataSync (avoids circular deps).
 *
 * Orchestration SoT: `runLiveCandleSync` + `live-candle-sync-context.ts` (dashboard + full).
 */

import type { RefObject } from 'react';

import type { CandlestickData } from '@/types/chart';
import { chartGapLog } from '@/utils/chart-gap-debug';
import { floorUtcCandlePeriodOpenSeconds, getTimeframeSeconds } from '@/utils/chart-time';
import { timestampToChartTime } from '@/utils/chart-timestamp';
import { shouldApplyTimeToTzForTimeframe, timeToTz } from '@/utils/chart-timezone';

import type { ISeriesApi, Time } from 'lightweight-charts';

const lastLiveUpdateKeyBySeries = new WeakMap<object, string>();

/**
 * SoT identity key for a candle's full OHLC tuple at a given time.
 *
 * Used by:
 *   - ``applyLiveCandleUpdate`` for ``WeakMap<series, lastKey>`` dedup of
 *     repeated WS ticks with the exact same OHLC.
 *   - ``computeTradingChartUnifiedSyncBuildRevisionKey`` for the unified-
 *     sync revision-key suffix that tracks live-candle identity.
 *
 * The two consumers had byte-identical local copies until 2026-05-30 —
 * exported here so a future format change (e.g. add volume to the
 * identity) propagates to every reader.
 */
export function buildCandleOhlcIdentityKey(candle: {
  // Accept both ``Time`` (LWC branded) and the raw numeric ``time`` carried
  // by our ``CandlestickData`` payloads. The key is identity-only — stringified.
  time: Time | number;
  open: number;
  high: number;
  low: number;
  close: number;
}): string {
  return `${String(candle.time)}:${candle.open}:${candle.high}:${candle.low}:${candle.close}`;
}

/**
 * Same as timestampToChartTime but returns null for invalid (callers that need null).
 * SoT: timestamp → seconds lives in chart-timestamp; this is the null-return variant.
 */
export function toNumericTimeSafe(t: unknown): number | null {
  const sec = timestampToChartTime(t);

  return Number.isFinite(sec) ? sec : null;
}

/**
 * Forming candle time from live candle (SoT for "current bar" time).
 * Used by sync effects and tooltip to exclude markers/indicators on the forming candle.
 */
export function getFormingCandleTime(
  liveCandle: CandlestickData | null | undefined
): number | null {
  if (liveCandle == null) return null;

  return toNumericTimeSafe(liveCandle.time);
}

/**
 * True when a Binance kline open time belongs on the chart timeframe grid and is
 * plausibly the forming bar after the last closed historical bar (or same-bar update).
 *
 * Rejects the TF-swap race where a 5m stream candle is merged into 15m REST history
 * (live open not divisible by chart period, or delta not a multiple of chart period).
 */
export function isLiveCandleAlignedWithChartHistory(
  liveUtc: number,
  lastHistoricalUtc: number,
  timeframe: string | undefined
): boolean {
  if (!timeframe) {
    return true;
  }

  const periodSec = getTimeframeSeconds(timeframe);

  if (periodSec <= 0) {
    return true;
  }

  if (!Number.isFinite(liveUtc) || !Number.isFinite(lastHistoricalUtc)) {
    return false;
  }

  const livePeriodOpen = floorUtcCandlePeriodOpenSeconds(timeframe, liveUtc);
  const lastPeriodOpen = floorUtcCandlePeriodOpenSeconds(timeframe, lastHistoricalUtc);

  // WS kline ``t`` must be the bucket open (BE/Binance convention; 1w = Monday, not epoch Thursday).
  if (livePeriodOpen !== liveUtc) {
    return false;
  }

  const delta = livePeriodOpen - lastPeriodOpen;

  if (delta < 0) {
    return false;
  }

  if (delta === 0 || delta === periodSec) {
    return true;
  }

  if (delta > periodSec && delta % periodSec === 0) {
    return true;
  }

  return false;
}

/**
 * Bug B watchdog (2026-05-30): the pre-fix code "snapped" the live bar back to
 * ``lastTime + period`` when live was multiple periods ahead of REST, which
 * mis-stamped T2's forming OHLC onto T1's slot and surfaced as a corrupted
 * just-closed bar on the full chart. Post-fix we always write at the live
 * bar's real slot — but we still want visibility when REST is lagging WS by
 * more than one period, so the operator can correlate against the
 * chart-indicators / OHLCV refetch path. Opt-in via DEBUG_CHART_GAP.
 */
function maybeWarnLiveBarAheadOfHistorical(
  liveTime: number,
  lastTime: number,
  timeframe: string | undefined
): void {
  if (!timeframe) return;
  const periodSec = getTimeframeSeconds(timeframe);

  if (periodSec <= 0 || liveTime <= lastTime + periodSec) return;

  chartGapLog('applyLiveCandleUpdate live ahead of historical by >1 period', {
    liveTime,
    lastTime,
    periodSec,
    periodsAhead: Math.round((liveTime - lastTime) / periodSec),
    timeframe,
    note: 'REST tail is lagging WS; rendering a visible gap until refetch catches up',
  });
}

function buildLiveCandleUpdate(
  liveCandle: CandlestickData,
  lastTime: number,
  timeframe: string | undefined
): { time: Time; open: number; high: number; low: number; close: number } | null {
  const liveTime = toNumericTimeSafe(liveCandle.time);

  if (liveTime === null || liveTime <= 0 || liveTime < lastTime) return null;

  maybeWarnLiveBarAheadOfHistorical(liveTime, lastTime, timeframe);

  return {
    time: liveTime as Time,
    open: liveCandle.open,
    high: liveCandle.high,
    low: liveCandle.low,
    close: liveCandle.close,
  };
}

/**
 * Apply live candle update to series. Shared by dashboard and full-chart sync.
 *
 * Dedup strategy: the per-series ``WeakMap<series, lastKey>`` below is the
 * SoT — two ticks with the same time + OHLC produce the same identity key
 * and the second is skipped. There is intentionally NO semantic threshold
 * filter (no "close moved < X%" filter, no "flat-tick" filter): LWC's
 * ``series.update`` with byte-identical OHLC is a no-op repaint and the
 * cost of a few micro-move repaints per second is dwarfed by the cost
 * (correctness + magic-number drift) of guessing what "actionable move"
 * means across timeframes / assets / leverage.
 */
export function applyLiveCandleUpdate(
  candleSeriesRef: RefObject<ISeriesApi<'Candlestick'> | null>,
  data: CandlestickData[],
  liveCandle: CandlestickData,
  timeframe?: string,
  timezone?: string
): void {
  if (!candleSeriesRef.current || data.length === 0) {
    return;
  }

  const lastBar = data[data.length - 1];
  const lastTime = toNumericTimeSafe(lastBar?.time);

  if (lastTime === null || lastTime <= 0 || !lastBar) {
    return;
  }

  let lwCandle = buildLiveCandleUpdate(liveCandle, lastTime, timeframe);

  if (!lwCandle) {
    return;
  }

  if (timezone) {
    const timeSec = typeof lwCandle.time === 'number' ? lwCandle.time : null;

    if (timeSec != null) {
      const afterTz = shouldApplyTimeToTzForTimeframe(timeframe)
        ? timeToTz(timeSec, timezone)
        : timeSec;

      lwCandle = { ...lwCandle, time: afterTz as Time };
    }
  }

  const series = candleSeriesRef.current;
  const dedupeKey = buildCandleOhlcIdentityKey(lwCandle);
  const previousKey = lastLiveUpdateKeyBySeries.get(series);

  if (previousKey === dedupeKey) {
    return;
  }

  lastLiveUpdateKeyBySeries.set(series, dedupeKey);
  traceLiveCandleSeriesUpdate(lwCandle, lastTime, lastBar.close, timeframe, timezone);

  try {
    series.update(lwCandle);
  } catch {
    // Library can throw e.g. "Cannot update oldest data"
  }
}

/**
 * Bug B diagnostic (2026-05-30, full chart 1px-bar artifact): opt-in via
 * localStorage.DEBUG_CHART_GAP=1. Captures the OHLC being written to which
 * bar time on each WS tick — distinguishes between an OHLC-corruption write
 * (T1 shows up with degenerate values AFTER its close moment) and a natural
 * small-body bar (T1's last real tick happened to have open===close).
 */
function traceLiveCandleSeriesUpdate(
  lwCandle: { time: Time; open: number; high: number; low: number; close: number },
  lastTime: number,
  lastHistoricalClose: number,
  timeframe: string | undefined,
  timezone: string | undefined
): void {
  // Diagnostic only: strict ``===`` is correct here — OHLC values come straight
  // from WS JSON.parse without intermediate arithmetic, so two equal-printed
  // numbers are byte-identical. A near-flat-but-not-exactly-flat bar is a
  // different signal (small body) and the ``bodyRatio`` field below already
  // captures it.
  const isFlat =
    lwCandle.open === lwCandle.close &&
    lwCandle.high === lwCandle.low &&
    lwCandle.open === lwCandle.high;

  chartGapLog('applyLiveCandleUpdate series.update', {
    barTime: lwCandle.time,
    open: lwCandle.open,
    high: lwCandle.high,
    low: lwCandle.low,
    close: lwCandle.close,
    isFlat,
    bodyRatio:
      Math.abs(lwCandle.close - lwCandle.open) / (Math.abs(lwCandle.high - lwCandle.low) || 1),
    lastHistoricalTime: lastTime,
    lastHistoricalClose,
    timeframe,
    timezoneApplied: Boolean(timezone),
  });
}
