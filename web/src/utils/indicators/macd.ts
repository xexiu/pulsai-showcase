// =============================================================================
// MACD (Moving Average Convergence Divergence) Calculator
// =============================================================================
//
// WHY MACD?
// - MACD line = Fast EMA - Slow EMA (trend direction)
// - Signal line = EMA of MACD (smoothed signal)
// - Histogram = MACD - Signal (momentum strength)
// - Crossovers indicate potential trend changes
//
// USAGE:
// const macdData = calculateMACD(candles, 12, 26, 9);
// =============================================================================

import { MACD } from '@thuantan2060/technicalindicators';

import type { CandlestickData } from '@/types/chart';

// =============================================================================
// Types
// =============================================================================

export interface MACDDataPoint {
  time: number;
  macd: number;
  signal: number;
  histogram: number;
}

// =============================================================================
// Constants
// =============================================================================

/** Default MACD fast EMA period */
export const DEFAULT_MACD_FAST_PERIOD = 12;

/** Default MACD slow EMA period */
export const DEFAULT_MACD_SLOW_PERIOD = 26;

/** Default MACD signal line period */
export const DEFAULT_MACD_SIGNAL_PERIOD = 9;

// =============================================================================
// Calculator Function
// =============================================================================

/**
 * Calculate MACD from candle close prices.
 *
 * ALGORITHM:
 * 1. Calculate fast EMA (12-period by default)
 * 2. Calculate slow EMA (26-period by default)
 * 3. MACD Line = Fast EMA - Slow EMA
 * 4. Signal Line = EMA of MACD Line (9-period by default)
 * 5. Histogram = MACD Line - Signal Line
 *
 * TRADING SIGNALS:
 * - MACD crosses above Signal → Bullish
 * - MACD crosses below Signal → Bearish
 * - Histogram > 0 = Bullish momentum
 * - Histogram < 0 = Bearish momentum
 *
 * @param candles - Array of OHLCV candle data
 * @param fastPeriod - Fast EMA period (default: 12)
 * @param slowPeriod - Slow EMA period (default: 26)
 * @param signalPeriod - Signal line period (default: 9)
 * @returns Array of MACD data points with timestamps
 *
 * @example
 * const macd = calculateMACD(candles, 12, 26, 9);
 * // macd: [{ time: 1700000000, macd: 120, signal: 115, histogram: 5 }, ...]
 */
export function calculateMACD(
  candles: CandlestickData[],
  fastPeriod: number = DEFAULT_MACD_FAST_PERIOD,
  slowPeriod: number = DEFAULT_MACD_SLOW_PERIOD,
  signalPeriod: number = DEFAULT_MACD_SIGNAL_PERIOD
): MACDDataPoint[] {
  // Need enough candles to calculate MACD
  if (candles.length < slowPeriod + signalPeriod) {
    return [];
  }

  const closes = candles.map((c) => c.close);
  const macdResult = MACD.calculate({
    values: closes,
    fastPeriod,
    slowPeriod,
    signalPeriod,
    SimpleMAOscillator: false,
    SimpleMASignal: false,
  });

  // Filter out undefined results and align with timestamps
  const validResults = macdResult.filter(
    (r): r is { MACD: number; signal: number; histogram: number } =>
      r.MACD !== undefined && r.signal !== undefined && r.histogram !== undefined
  );

  const startIndex = candles.length - validResults.length;

  return validResults.map((result, i) => {
    const candle = candles[startIndex + i];

    return {
      time: (candle?.time ?? 0) as number,
      macd: result.MACD,
      signal: result.signal,
      histogram: result.MACD - result.signal, // Recalculate for precision
    };
  });
}
