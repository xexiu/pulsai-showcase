// @vitest-environment node
// =============================================================================
// MACD Calculator Tests
// =============================================================================

import { describe, expect, it } from 'vitest';

import type { CandlestickData } from '@/types/chart';
import {
  calculateMACD,
  DEFAULT_MACD_FAST_PERIOD,
  DEFAULT_MACD_SIGNAL_PERIOD,
  DEFAULT_MACD_SLOW_PERIOD,
} from '@/utils/indicators/macd';

// =============================================================================
// Test Data
// =============================================================================

function createCandles(count: number, baseClose = 100): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: baseClose + Math.random() * 10 - 5,
    high: baseClose + Math.random() * 10,
    low: baseClose - Math.random() * 10,
    close: baseClose + (i % 2 === 0 ? i * 0.5 : -i * 0.3),
  }));
}

function createUptrendCandles(count: number): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: 100 + i * 2,
    high: 100 + i * 2 + 1,
    low: 100 + i * 2 - 0.5,
    close: 100 + i * 2 + 0.8,
  }));
}

function createDowntrendCandles(count: number): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: 200 - i * 2,
    high: 200 - i * 2 + 0.5,
    low: 200 - i * 2 - 1,
    close: 200 - i * 2 - 0.8,
  }));
}

// =============================================================================
// Tests
// =============================================================================

describe('calculateMACD', () => {
  describe('edge cases', () => {
    it('returns empty array when candles < slowPeriod + signalPeriod', () => {
      const candles = createCandles(30); // Need at least 35 (26 + 9)

      const result = calculateMACD(candles, 12, 26, 9);

      expect(result).toEqual([]);
    });

    it('returns empty array for empty candles', () => {
      const result = calculateMACD([], 12, 26, 9);

      expect(result).toEqual([]);
    });

    it('returns empty array for insufficient data', () => {
      const candles = createCandles(10);

      const result = calculateMACD(candles);

      expect(result).toEqual([]);
    });
  });

  describe('with valid data', () => {
    it('returns MACD values when enough data is provided', () => {
      const candles = createCandles(60);
      const result = calculateMACD(candles);

      expect(result.length).toBeGreaterThan(0);
    });

    it('each data point has all required fields', () => {
      const candles = createCandles(60);
      const result = calculateMACD(candles);

      const point = result[0];

      expect(point).toHaveProperty('time');
      expect(point).toHaveProperty('macd');
      expect(point).toHaveProperty('signal');
      expect(point).toHaveProperty('histogram');
    });

    it('histogram equals MACD minus signal', () => {
      const candles = createCandles(60);
      const result = calculateMACD(candles);

      for (const point of result) {
        const expectedHistogram = point.macd - point.signal;

        expect(point.histogram).toBeCloseTo(expectedHistogram, 5);
      }
    });

    it('aligns MACD values with candle timestamps', () => {
      const candles = createCandles(60);
      const result = calculateMACD(candles);

      const firstMacdTime = result[0]?.time;

      expect(firstMacdTime).toBeDefined();
      expect(candles.some((c) => c.time === firstMacdTime)).toBe(true);
    });
  });

  describe('trend detection', () => {
    it('MACD is positive in strong uptrend', () => {
      const candles = createUptrendCandles(60);
      const result = calculateMACD(candles);

      // In strong uptrend, MACD should be positive (fast EMA > slow EMA)
      const lastMacd = result[result.length - 1]?.macd ?? 0;

      expect(lastMacd).toBeGreaterThan(0);
    });

    it('MACD is negative in strong downtrend', () => {
      const candles = createDowntrendCandles(60);
      const result = calculateMACD(candles);

      // In strong downtrend, MACD should be negative (fast EMA < slow EMA)
      const lastMacd = result[result.length - 1]?.macd ?? 0;

      expect(lastMacd).toBeLessThan(0);
    });
  });

  describe('with custom periods', () => {
    it('works with shorter periods (8, 17, 9)', () => {
      const candles = createCandles(50);
      const result = calculateMACD(candles, 8, 17, 9);

      expect(result.length).toBeGreaterThan(0);
    });

    it('works with longer periods (12, 26, 12)', () => {
      const candles = createCandles(80);
      const result = calculateMACD(candles, 12, 26, 12);

      expect(result.length).toBeGreaterThan(0);
    });

    it('shorter slow period produces more data points', () => {
      const candles = createCandles(80);
      const shortSlow = calculateMACD(candles, 12, 20, 9);
      const longSlow = calculateMACD(candles, 12, 30, 9);

      expect(shortSlow.length).toBeGreaterThanOrEqual(longSlow.length);
    });
  });

  describe('default period constants', () => {
    it('DEFAULT_MACD_FAST_PERIOD is 12', () => {
      expect(DEFAULT_MACD_FAST_PERIOD).toBe(12);
    });

    it('DEFAULT_MACD_SLOW_PERIOD is 26', () => {
      expect(DEFAULT_MACD_SLOW_PERIOD).toBe(26);
    });

    it('DEFAULT_MACD_SIGNAL_PERIOD is 9', () => {
      expect(DEFAULT_MACD_SIGNAL_PERIOD).toBe(9);
    });
  });
});
