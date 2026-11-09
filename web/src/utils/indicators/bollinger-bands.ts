// =============================================================================
// Bollinger Bands Calculator
// =============================================================================
//
// WHY BOLLINGER BANDS?
// - Upper/Lower bands = SMA ± (stdDev * multiplier)
// - Price near lower = potential buy, near upper = potential sell
// - Band squeeze = low volatility, breakout expected
//
// USAGE:
// const bbData = calculateBollingerBands(candles, 20, 2);
// =============================================================================

import { BollingerBands } from '@thuantan2060/technicalindicators';

import type { CandlestickData } from '@/types/chart';

// =============================================================================
// Types
// =============================================================================

export interface BollingerBandsDataPoint {
  time: number;
  upper: number;
  middle: number;
  lower: number;
}

// =============================================================================
// Constants
// =============================================================================

/** Default BB period (20-day SMA is standard) */
export const DEFAULT_BB_PERIOD = 20;

/** Default BB standard deviation multiplier */
export const DEFAULT_BB_STD_DEV = 2;

// =============================================================================
// Calculator Function
// =============================================================================

/**
 * Calculate Bollinger Bands from candle close prices.
 *
 * ALGORITHM:
 * 1. Calculate SMA (Simple Moving Average) over period
 * 2. Calculate standard deviation over period
 * 3. Upper Band = SMA + (stdDev * multiplier)
 * 4. Lower Band = SMA - (stdDev * multiplier)
 *
 * TRADING SIGNALS:
 * - Price touches upper band → Potential overbought (sell)
 * - Price touches lower band → Potential oversold (buy)
 * - Bands squeeze together → Low volatility, expect breakout
 * - Bands widen → High volatility period
 *
 * BAND WIDTH ANALYSIS:
 * - Narrow bands: Low volatility, consolidation
 * - Wide bands: High volatility, trending market
 *
 * @param candles - Array of OHLCV candle data
 * @param period - SMA period (default: 20)
 * @param stdDev - Standard deviation multiplier (default: 2)
 * @returns Array of Bollinger Bands data points
 *
 * @example
 * const bb = calculateBollingerBands(candles, 20, 2);
 * // bb: [{ time: 1700000000, upper: 51000, middle: 50000, lower: 49000 }, ...]
 */
export function calculateBollingerBands(
  candles: CandlestickData[],
  period: number = DEFAULT_BB_PERIOD,
  stdDev: number = DEFAULT_BB_STD_DEV
): BollingerBandsDataPoint[] {
  // Need at least period + 1 candles for first BB value
  if (candles.length < period + 1) {
    return [];
  }

  const closes = candles.map((c) => c.close);
  const bbResult = BollingerBands.calculate({
    values: closes,
    period,
    stdDev,
  });

  const startIndex = candles.length - bbResult.length;

  return bbResult.map((result, i) => {
    const candle = candles[startIndex + i];

    return {
      time: (candle?.time ?? 0) as number,
      upper: result.upper,
      middle: result.middle,
      lower: result.lower,
    };
  });
}
