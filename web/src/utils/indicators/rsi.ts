// =============================================================================
// RSI (Relative Strength Index) Calculator
// =============================================================================
//
// WHY RSI?
// - Values 0-100: < 30 = oversold, > 70 = overbought
// - Classic momentum indicator for reversal signals
// - One of the most widely used technical indicators
//
// USAGE:
// const rsiData = calculateRSI(candles, 14);
// =============================================================================

import { RSI } from '@thuantan2060/technicalindicators';

import type { CandlestickData } from '@/types/chart';

// =============================================================================
// Types
// =============================================================================

export interface RSIDataPoint {
  time: number;
  value: number;
}

// =============================================================================
// Constants
// =============================================================================

/** Default RSI period (industry standard) */
export const DEFAULT_RSI_PERIOD = 14;

// =============================================================================
// Calculator Function
// =============================================================================

/**
 * Calculate RSI from candle close prices.
 *
 * ALGORITHM:
 * 1. Calculate price changes (close - previous close)
 * 2. Separate gains and losses
 * 3. Calculate average gain and loss over period
 * 4. RS = Average Gain / Average Loss
 * 5. RSI = 100 - (100 / (1 + RS))
 *
 * @param candles - Array of OHLCV candle data
 * @param period - RSI period (default: 14)
 * @returns Array of RSI data points with timestamps
 *
 * @example
 * const rsi = calculateRSI(candles, 14);
 * // rsi: [{ time: 1700000000, value: 45.2 }, ...]
 */
export function calculateRSI(
  candles: CandlestickData[],
  period: number = DEFAULT_RSI_PERIOD
): RSIDataPoint[] {
  // Need at least period + 1 candles to calculate first RSI value
  if (candles.length < period + 1) {
    return [];
  }

  const closes = candles.map((c) => c.close);
  const rsiValues = RSI.calculate({ values: closes, period });

  // Align RSI values with candle timestamps
  // RSI needs `period` candles to produce first value
  const startIndex = candles.length - rsiValues.length;

  return rsiValues.map((value, i) => {
    const candle = candles[startIndex + i];

    return {
      time: (candle?.time ?? 0) as number,
      value,
    };
  });
}
