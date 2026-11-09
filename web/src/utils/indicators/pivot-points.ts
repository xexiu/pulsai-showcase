// =============================================================================
// Pivot Points Calculator
// =============================================================================
//
// WHY PIVOT POINTS?
// - Classic support/resistance levels used by floor traders since 1930s
// - Self-fulfilling prophecy: Many traders watch these levels
// - Works best for intraday/day trading
//
// CRITICAL: Pivot points use PERIOD aggregate (not single candle!)
// - High = HIGHEST high across the period (e.g., 24 hourly candles = 1 day)
// - Low = LOWEST low across the period
// - Close = Last candle's close
//
// USAGE:
// const pivots = calculatePivotPoints(candles, 24); // 24h for hourly charts
// =============================================================================

import type { CandlestickData } from '@/types/chart';

// =============================================================================
// Types
// =============================================================================

export interface PivotPointDataPoint {
  /** Pivot Point (center line) */
  pp: number;
  /** First Resistance level */
  r1: number;
  /** Second Resistance level */
  r2: number;
  /** First Support level */
  s1: number;
  /** Second Support level */
  s2: number;
  /** Start time for horizontal line rendering */
  startTime: number;
  /** End time for horizontal line rendering */
  endTime: number;
}

/** Aggregated high/low/close from a period of candles */
interface PeriodAggregate {
  high: number;
  low: number;
  close: number;
  isValid: boolean;
}

// =============================================================================
// Constants
// =============================================================================

/**
 * Default pivot period for hourly charts.
 *
 * WHY 24?
 * - 24 hourly candles = 1 day
 * - Pivot points traditionally calculated from previous day's range
 * - For other timeframes: 4h = 6 candles/day, 15m = 96 candles/day
 */
export const DEFAULT_PIVOT_PERIOD = 24;

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Aggregate high/low/close from a period of candles.
 *
 * WHY AGGREGATE?
 * - Single candle has tiny range (~$68 for BTC hourly)
 * - Period aggregate captures full day's range (~$3000+ for BTC)
 * - Produces meaningful support/resistance levels
 */
function aggregatePeriod(periodCandles: CandlestickData[]): PeriodAggregate {
  let periodHigh = -Infinity;
  let periodLow = Infinity;

  for (const candle of periodCandles) {
    if (candle.high > periodHigh) {
      periodHigh = candle.high;
    }

    if (candle.low < periodLow) {
      periodLow = candle.low;
    }
  }

  const lastCandle = periodCandles[periodCandles.length - 1];
  const periodClose = lastCandle?.close ?? 0;

  const isValid = periodHigh !== -Infinity && periodLow !== Infinity && periodClose !== 0;

  return { high: periodHigh, low: periodLow, close: periodClose, isValid };
}

/**
 * Calculate pivot levels from aggregated H/L/C.
 *
 * FORMULAS (Classic Pivot Points):
 * - PP = (High + Low + Close) / 3
 * - R1 = (2 × PP) - Low
 * - R2 = PP + (High - Low)
 * - S1 = (2 × PP) - High
 * - S2 = PP - (High - Low)
 */
function calculateLevels(aggregate: PeriodAggregate): {
  pp: number;
  r1: number;
  r2: number;
  s1: number;
  s2: number;
} {
  const { high, low, close } = aggregate;
  const pp = (high + low + close) / 3;
  const range = high - low;

  return {
    pp,
    r1: 2 * pp - low,
    r2: pp + range,
    s1: 2 * pp - high,
    s2: pp - range,
  };
}

// =============================================================================
// Main Calculator Function
// =============================================================================

/**
 * Select candles that fall in the previous completed period (TradingView parity).
 *
 * Pivots use previous period's H/L/C, not "last N bars" (which can span two periods).
 * E.g. for 4h at Tue 12:00 we use Mon 00:00–Mon 24:00, not Mon 12:00–Tue 12:00.
 */
function candlesInPreviousPeriod(
  candles: CandlestickData[],
  periodSeconds: number
): CandlestickData[] {
  if (candles.length === 0) return [];
  const lastTime = candles[candles.length - 1]!.time;
  const startOfPrevPeriod = Math.floor(lastTime / periodSeconds) * periodSeconds - periodSeconds;
  const endOfPrevPeriod = startOfPrevPeriod + periodSeconds;
  const filtered = candles.filter((c) => c.time >= startOfPrevPeriod && c.time < endOfPrevPeriod);

  return filtered.sort((a, b) => a.time - b.time);
}

/**
 * Snap the pivot line's start to a real candle bar time.
 *
 * WHY: ``Math.floor(t / periodSeconds) * periodSeconds`` anchors to the
 * UNIX-epoch grid (Thursday for weeks, midnight for days). Exchange candles
 * don't always align to that grid — Binance weekly bars open on Monday, so
 * the epoch-aligned Thursday is NOT a candle bar time. Passing an off-grid
 * time to lightweight-charts allocates a new logical-index slot between the
 * previous and current bars (visible as a "displacement" gap when Pivot
 * Points toggles on, most noticeable on 1w). Returning the first candle
 * inside the current period guarantees ``startTime`` lays out on an
 * existing logical index. Falls back to ``lastTime`` if no candle is in
 * range (then ``endTime <= startTime`` routes to the empty-arrays branch
 * in ``convertPivotPointsToLW``, hiding the series cleanly).
 */
function snapStartTimeToCandleBar(
  candles: CandlestickData[],
  lastTime: number,
  periodSeconds: number
): number {
  const computedPeriodStart = Math.floor(lastTime / periodSeconds) * periodSeconds;
  const firstCandleInCurrentPeriod = candles.find((c) => c.time >= computedPeriodStart);

  return firstCandleInCurrentPeriod?.time ?? lastTime;
}

/**
 * Calculate Pivot Points using Classic formula from period's aggregate H/L/C.
 *
 * TRADINGVIEW PARITY:
 * - When periodSeconds is provided: use candles in the **previous completed period**
 *   (e.g. previous calendar day), not "last N bars". Line is drawn from start of
 *   **current** period to end of chart so pivots don't stretch from chart start.
 * - When periodSeconds is omitted: legacy behavior (last N bars, line from candles[0]).
 *
 * TRADING SIGNALS:
 * - Price bounces off S1/S2 → Buy signal
 * - Price bounces off R1/R2 → Sell signal
 *
 * @param candles - Array of OHLCV candle data (time in Unix seconds)
 * @param period - Number of candles for period (e.g. 6 for 4h = 1 day)
 * @param periodSeconds - Optional. Period length in seconds (86400 = daily). When set, anchors to previous period.
 * @returns Pivot point data or null if not enough data
 */
export function calculatePivotPoints(
  candles: CandlestickData[],
  period: number = DEFAULT_PIVOT_PERIOD,
  periodSeconds?: number
): PivotPointDataPoint | null {
  if (candles.length === 0) return null;

  let periodCandles: CandlestickData[];
  let startTime: number;
  let endTime: number;

  if (periodSeconds !== undefined && periodSeconds > 0) {
    periodCandles = candlesInPreviousPeriod(candles, periodSeconds);
    if (periodCandles.length === 0) {
      periodCandles = candles.slice(-period);
      if (periodCandles.length < period) return null;
    }
    const lastTime = candles[candles.length - 1]!.time;

    startTime = snapStartTimeToCandleBar(candles, lastTime, periodSeconds);
    endTime = lastTime;
  } else {
    if (candles.length < period) return null;
    periodCandles = candles.slice(-period);
    startTime = candles[0]?.time ?? 0;
    endTime = periodCandles[periodCandles.length - 1]?.time ?? 0;
  }

  if (periodCandles.length === 0) return null;

  const aggregate = aggregatePeriod(periodCandles);

  if (!aggregate.isValid) return null;

  const levels = calculateLevels(aggregate);

  return { ...levels, startTime, endTime };
}

/**
 * Group candles into ordered period buckets keyed by the epoch-aligned period
 * index (``floor(time / periodSeconds)``).
 *
 * Daily buckets align to UTC midnight; weekly candles (Monday-open) each fall
 * alone in their own bucket, so real candle times — not the epoch-aligned key —
 * are used as segment boundaries downstream (no off-grid displacement).
 */
function groupCandlesByPeriod(
  candles: CandlestickData[],
  periodSeconds: number
): CandlestickData[][] {
  const byKey = new Map<number, CandlestickData[]>();

  for (const candle of candles) {
    const key = Math.floor(candle.time / periodSeconds);
    const bucket = byKey.get(key);

    if (bucket) {
      bucket.push(candle);
    } else {
      byKey.set(key, [candle]);
    }
  }

  return [...byKey.keys()].sort((a, b) => a - b).map((key) => byKey.get(key)!);
}

/**
 * Calculate a SEQUENCE of Classic Pivot Points — one per completed period.
 *
 * WHY (vs single {@link calculatePivotPoints}):
 * - High timeframes (4h/1d/1w) fit only 1–6 candles in the current period, so a
 *   single pivot renders as a short right-edge stub. Emitting one pivot per
 *   period populates the whole pane with levels (TradingView "pivots back").
 *
 * CLASSIC RULE: period P's H/L/C drives the levels shown DURING the next period
 * P+1. So each returned point uses the PREVIOUS bucket's aggregate and spans the
 * CURRENT bucket's real candle times (``startTime``/``endTime``). N buckets ⇒
 * N−1 points; the last point equals {@link calculatePivotPoints} for parity.
 *
 * Rendered with ``LineType.WithSteps`` so each level holds flat within its period
 * and steps at the boundary (see ``convertPivotPointsSeriesToLW``).
 *
 * @param candles - OHLCV candles (time in Unix seconds), ascending.
 * @param periodSeconds - Period length in seconds (86400 daily, 604800 weekly).
 * @returns Pivot points oldest→newest; empty when fewer than two periods exist.
 */
export function calculatePivotPointsSeries(
  candles: CandlestickData[],
  periodSeconds: number
): PivotPointDataPoint[] {
  if (periodSeconds <= 0 || candles.length === 0) return [];

  const buckets = groupCandlesByPeriod(candles, periodSeconds);

  if (buckets.length < 2) return [];

  const series: PivotPointDataPoint[] = [];

  for (let index = 1; index < buckets.length; index += 1) {
    const previousBucket = buckets[index - 1]!;
    const applyBucket = buckets[index]!;

    const aggregate = aggregatePeriod(previousBucket);

    if (!aggregate.isValid) continue;

    const levels = calculateLevels(aggregate);

    series.push({
      ...levels,
      startTime: applyBucket[0]!.time,
      endTime: applyBucket[applyBucket.length - 1]!.time,
    });
  }

  return series;
}
