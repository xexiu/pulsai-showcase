// @vitest-environment node
// =============================================================================
// Bollinger Bands Calculator Tests
// =============================================================================

import { describe, expect, it } from 'vitest';

import type { CandlestickData } from '@/types/chart';
import {
  calculateBollingerBands,
  DEFAULT_BB_PERIOD,
  DEFAULT_BB_STD_DEV,
} from '@/utils/indicators/bollinger-bands';

// =============================================================================
// Test Data
// =============================================================================

function createCandles(count: number, baseClose = 100): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: baseClose + Math.random() * 10 - 5,
    high: baseClose + Math.random() * 10,
    low: baseClose - Math.random() * 10,
    close: baseClose + (i % 2 === 0 ? i * 0.3 : -i * 0.2),
  }));
}

function createFlatCandles(count: number, closePrice = 100): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: closePrice,
    high: closePrice + 0.5,
    low: closePrice - 0.5,
    close: closePrice, // All closes are the same
  }));
}

function createVolatileCandles(count: number): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: 100 + Math.random() * 50 - 25,
    high: 150 + Math.random() * 20,
    low: 50 + Math.random() * 20,
    close: 100 + (i % 2 === 0 ? 30 : -30), // Wide swings
  }));
}

// =============================================================================
// Tests
// =============================================================================

describe('calculateBollingerBands', () => {
  describe('edge cases', () => {
    it('returns empty array when candles < period + 1', () => {
      const candles = createCandles(15); // Need at least 21 for default period 20

      const result = calculateBollingerBands(candles, 20, 2);

      expect(result).toEqual([]);
    });

    it('returns empty array for empty candles', () => {
      const result = calculateBollingerBands([], 20, 2);

      expect(result).toEqual([]);
    });

    it('returns empty array for single candle', () => {
      const result = calculateBollingerBands([createCandles(1)[0]!], 20, 2);

      expect(result).toEqual([]);
    });
  });

  describe('with valid data', () => {
    it('returns BB values when enough data is provided', () => {
      const candles = createCandles(40);
      const result = calculateBollingerBands(candles);

      expect(result.length).toBeGreaterThan(0);
    });

    it('each data point has all required fields', () => {
      const candles = createCandles(40);
      const result = calculateBollingerBands(candles);

      const point = result[0];

      expect(point).toHaveProperty('time');
      expect(point).toHaveProperty('upper');
      expect(point).toHaveProperty('middle');
      expect(point).toHaveProperty('lower');
    });

    it('upper band is above middle band', () => {
      const candles = createCandles(40);
      const result = calculateBollingerBands(candles);

      for (const point of result) {
        expect(point.upper).toBeGreaterThan(point.middle);
      }
    });

    it('lower band is below middle band', () => {
      const candles = createCandles(40);
      const result = calculateBollingerBands(candles);

      for (const point of result) {
        expect(point.lower).toBeLessThan(point.middle);
      }
    });

    it('bands are symmetric around middle (same distance)', () => {
      const candles = createCandles(40);
      const result = calculateBollingerBands(candles);

      for (const point of result) {
        const upperDiff = point.upper - point.middle;
        const lowerDiff = point.middle - point.lower;

        expect(upperDiff).toBeCloseTo(lowerDiff, 5);
      }
    });

    it('aligns BB values with candle timestamps', () => {
      const candles = createCandles(40);
      const result = calculateBollingerBands(candles);

      const firstBBTime = result[0]?.time;

      expect(firstBBTime).toBeDefined();
      expect(candles.some((c) => c.time === firstBBTime)).toBe(true);
    });
  });

  describe('volatility detection', () => {
    it('narrow bands for low volatility (flat prices)', () => {
      const candles = createFlatCandles(40);
      const result = calculateBollingerBands(candles);

      // For flat prices, bands should be very narrow
      const lastBB = result[result.length - 1]!;
      const bandwidth = lastBB.upper - lastBB.lower;

      // Bandwidth should be very small for flat prices
      expect(bandwidth).toBeLessThan(5);
    });

    it('wide bands for high volatility', () => {
      const candles = createVolatileCandles(40);
      const result = calculateBollingerBands(candles);

      const lastBB = result[result.length - 1]!;
      const bandwidth = lastBB.upper - lastBB.lower;

      // Bandwidth should be wider for volatile prices
      expect(bandwidth).toBeGreaterThan(10);
    });
  });

  describe('with custom parameters', () => {
    it('works with shorter period (10)', () => {
      const candles = createCandles(30);
      const result = calculateBollingerBands(candles, 10, 2);

      expect(result.length).toBeGreaterThan(0);
    });

    it('works with longer period (50)', () => {
      const candles = createCandles(80);
      const result = calculateBollingerBands(candles, 50, 2);

      expect(result.length).toBeGreaterThan(0);
    });

    it('shorter period produces more data points', () => {
      const candles = createCandles(80);
      const shortPeriod = calculateBollingerBands(candles, 10, 2);
      const longPeriod = calculateBollingerBands(candles, 30, 2);

      expect(shortPeriod.length).toBeGreaterThan(longPeriod.length);
    });

    it('higher stdDev produces wider bands', () => {
      const candles = createCandles(40);
      const narrow = calculateBollingerBands(candles, 20, 1);
      const wide = calculateBollingerBands(candles, 20, 3);

      const narrowWidth = narrow[0]!.upper - narrow[0]!.lower;
      const wideWidth = wide[0]!.upper - wide[0]!.lower;

      expect(wideWidth).toBeGreaterThan(narrowWidth);
    });
  });

  describe('default constants', () => {
    it('DEFAULT_BB_PERIOD is 20', () => {
      expect(DEFAULT_BB_PERIOD).toBe(20);
    });

    it('DEFAULT_BB_STD_DEV is 2', () => {
      expect(DEFAULT_BB_STD_DEV).toBe(2);
    });
  });
});
