// @vitest-environment node
// =============================================================================
// RSI Calculator Tests
// =============================================================================

import { describe, expect, it } from 'vitest';

import type { CandlestickData } from '@/types/chart';
import { calculateRSI, DEFAULT_RSI_PERIOD } from '@/utils/indicators/rsi';

// =============================================================================
// Test Data
// =============================================================================

function createCandles(count: number, baseClose = 100): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600, // 1 hour intervals
    open: baseClose + Math.random() * 10 - 5,
    high: baseClose + Math.random() * 10,
    low: baseClose - Math.random() * 10,
    close: baseClose + (i % 2 === 0 ? i * 0.5 : -i * 0.3), // Alternating trend
  }));
}

// Create candles with a clear uptrend (RSI should be high)
function createUptrendCandles(count: number): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: 100 + i * 2,
    high: 100 + i * 2 + 1,
    low: 100 + i * 2 - 0.5,
    close: 100 + i * 2 + 0.8, // Consistently closing higher
  }));
}

// Create candles with a clear downtrend (RSI should be low)
function createDowntrendCandles(count: number): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: 200 - i * 2,
    high: 200 - i * 2 + 0.5,
    low: 200 - i * 2 - 1,
    close: 200 - i * 2 - 0.8, // Consistently closing lower
  }));
}

// =============================================================================
// Tests
// =============================================================================

describe('calculateRSI', () => {
  describe('edge cases', () => {
    it('returns empty array when candles length is less than period + 1', () => {
      const candles = createCandles(10);
      const result = calculateRSI(candles, 14); // Need at least 15 candles

      expect(result).toEqual([]);
    });

    it('returns empty array for empty candles', () => {
      const result = calculateRSI([], 14);

      expect(result).toEqual([]);
    });

    it('returns empty array for single candle', () => {
      const result = calculateRSI([createCandles(1)[0]!], 14);

      expect(result).toEqual([]);
    });
  });

  describe('with valid data', () => {
    it('returns RSI values when enough data is provided', () => {
      const candles = createCandles(30);
      const result = calculateRSI(candles, DEFAULT_RSI_PERIOD);

      expect(result.length).toBeGreaterThan(0);
      expect(result[0]).toHaveProperty('time');
      expect(result[0]).toHaveProperty('value');
    });

    it('aligns RSI values with candle timestamps', () => {
      const candles = createCandles(30);
      const result = calculateRSI(candles, 14);

      // First RSI value should have a timestamp from the candles
      const firstRsiTime = result[0]?.time;

      expect(firstRsiTime).toBeDefined();
      expect(candles.some((c) => c.time === firstRsiTime)).toBe(true);
    });

    it('RSI values are within 0-100 range', () => {
      const candles = createCandles(50);
      const result = calculateRSI(candles, 14);

      for (const point of result) {
        expect(point.value).toBeGreaterThanOrEqual(0);
        expect(point.value).toBeLessThanOrEqual(100);
      }
    });

    it('returns high RSI (>50) for consistent uptrend', () => {
      const candles = createUptrendCandles(30);
      const result = calculateRSI(candles, 14);

      // Last RSI value should be high for uptrend
      const lastRsi = result[result.length - 1]?.value ?? 0;

      expect(lastRsi).toBeGreaterThan(50);
    });

    it('returns low RSI (<50) for consistent downtrend', () => {
      const candles = createDowntrendCandles(30);
      const result = calculateRSI(candles, 14);

      // Last RSI value should be low for downtrend
      const lastRsi = result[result.length - 1]?.value ?? 100;

      expect(lastRsi).toBeLessThan(50);
    });
  });

  describe('with custom period', () => {
    it('works with period of 7', () => {
      const candles = createCandles(20);
      const result = calculateRSI(candles, 7);

      expect(result.length).toBeGreaterThan(0);
    });

    it('works with period of 21', () => {
      const candles = createCandles(50);
      const result = calculateRSI(candles, 21);

      expect(result.length).toBeGreaterThan(0);
    });

    it('shorter period produces more data points', () => {
      const candles = createCandles(50);
      const shortPeriod = calculateRSI(candles, 7);
      const longPeriod = calculateRSI(candles, 21);

      expect(shortPeriod.length).toBeGreaterThan(longPeriod.length);
    });
  });

  describe('default period constant', () => {
    it('DEFAULT_RSI_PERIOD is 14 (industry standard)', () => {
      expect(DEFAULT_RSI_PERIOD).toBe(14);
    });
  });
});
