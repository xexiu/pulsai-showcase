// @vitest-environment node
// =============================================================================
// Pivot Points Calculator Tests
// =============================================================================
//
// CRITICAL: Tests must verify BUSINESS LOGIC, not just math!
// - Pivot points aggregate High/Low across the ENTIRE period
// - NOT just the last candle's H/L/C
// =============================================================================

import { describe, expect, it } from 'vitest';

import type { CandlestickData } from '@/types/chart';
import {
  calculatePivotPoints,
  calculatePivotPointsSeries,
  DEFAULT_PIVOT_PERIOD,
} from '@/utils/indicators/pivot-points';

// =============================================================================
// Test Data
// =============================================================================

function createCandles(count: number, basePrice = 100): CandlestickData[] {
  return Array.from({ length: count }, (_, i) => ({
    time: 1700000000 + i * 3600,
    open: basePrice,
    high: basePrice + 10 + i * 2, // Increasing highs
    low: basePrice - 10 - i * 2, // Decreasing lows (wider range over time)
    close: basePrice + (i % 2 === 0 ? 5 : -5),
  }));
}

function createSpecificCandle(
  high: number,
  low: number,
  close: number,
  time: number
): CandlestickData {
  return {
    time,
    open: (high + low) / 2,
    high,
    low,
    close,
  };
}

// =============================================================================
// Tests
// =============================================================================

describe('calculatePivotPoints', () => {
  describe('edge cases', () => {
    it('returns null for empty candles', () => {
      const result = calculatePivotPoints([]);

      expect(result).toBeNull();
    });

    it('returns null when candles < period', () => {
      const candles = createCandles(10);

      const result = calculatePivotPoints(candles, 24); // Need 24, only have 10

      expect(result).toBeNull();
    });
  });

  describe('period aggregation (CRITICAL - this is what was broken)', () => {
    it('uses HIGHEST high across entire period, not just last candle', () => {
      // Create candles where the HIGHEST high is NOT in the last candle
      const candles: CandlestickData[] = [
        createSpecificCandle(150, 80, 100, 1700000000), // HIGHEST high = 150
        createSpecificCandle(110, 90, 105, 1700003600),
        createSpecificCandle(105, 85, 95, 1700007200), // Last candle, high = 105
      ];

      const result = calculatePivotPoints(candles, 3);

      // R2 = PP + (High - Low), so if using period high (150), R2 will be much higher
      // If bug existed (using last candle's high=105), R2 would be lower
      expect(result).not.toBeNull();

      // Period High should be 150, not 105
      // PP = (150 + 80 + 95) / 3 = 108.33
      // R2 = PP + (150 - 80) = 108.33 + 70 = 178.33
      expect(result!.r2).toBeCloseTo(108.33 + 70, 0);
    });

    it('uses LOWEST low across entire period, not just last candle', () => {
      // Create candles where the LOWEST low is NOT in the last candle
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 50, 100, 1700000000), // LOWEST low = 50
        createSpecificCandle(115, 90, 105, 1700003600),
        createSpecificCandle(110, 95, 100, 1700007200), // Last candle, low = 95
      ];

      const result = calculatePivotPoints(candles, 3);

      // S2 = PP - (High - Low), so if using period low (50), S2 will be much lower
      // If bug existed (using last candle's low=95), S2 would be higher
      expect(result).not.toBeNull();

      // Period High = 120, Period Low = 50, Close = 100
      // PP = (120 + 50 + 100) / 3 = 90
      // S2 = PP - (120 - 50) = 90 - 70 = 20
      expect(result!.s2).toBeCloseTo(90 - 70, 0);
    });

    it('produces meaningful spread between R2 and S2 (not clustered)', () => {
      // Real-world scenario: 24 hourly BTC candles with ~$3000 daily range
      const candles: CandlestickData[] = [];
      const baseTime = 1700000000;

      for (let i = 0; i < 24; i++) {
        // Simulate realistic BTC hourly candles with varying H/L
        const high = 90000 + Math.random() * 2000; // 90,000 - 92,000
        const low = 87000 + Math.random() * 2000; // 87,000 - 89,000
        const close = (high + low) / 2;

        candles.push(createSpecificCandle(high, low, close, baseTime + i * 3600));
      }

      const result = calculatePivotPoints(candles, 24);

      expect(result).not.toBeNull();

      // The spread between R2 and S2 should be roughly 2x the period range
      // Period range is approximately (max high - min low) ≈ $5000
      // R2 - S2 = 2 * range ≈ $10,000
      const spread = result!.r2 - result!.s2;

      expect(spread).toBeGreaterThan(5000); // Should be meaningful, not ~$100
    });

    it('BUG REPRODUCTION: clustered levels indicate broken implementation', () => {
      // This test reproduces the bug where all levels were clustered
      // If using only last candle's H/L (~$68 range), spread would be ~$136
      // If using period aggregate (~$3000 range), spread would be ~$6000

      const candles: CandlestickData[] = [];
      const baseTime = 1700000000;

      // Create 24 candles with cumulative price movement (like real BTC)
      let price = 88000;

      for (let i = 0; i < 24; i++) {
        // Each candle has small range (~$100), but overall range is large
        price += (Math.random() - 0.5) * 500; // Random walk
        const candleHigh = price + 50;
        const candleLow = price - 50;

        candles.push(createSpecificCandle(candleHigh, candleLow, price, baseTime + i * 3600));
      }

      const result = calculatePivotPoints(candles, 24);

      expect(result).not.toBeNull();

      // The spread should NOT be tiny (< $500) like in the buggy version
      const spread = result!.r2 - result!.s2;

      expect(spread).toBeGreaterThan(500);
    });
  });

  describe('formula correctness', () => {
    it('calculates PP correctly: (periodHigh + periodLow + close) / 3', () => {
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, 1700000000), // H=120, L=80
        createSpecificCandle(110, 90, 95, 1700003600), // Close=95
      ];

      const result = calculatePivotPoints(candles, 2);
      // Period High=120, Period Low=80, Close=95
      // PP = (120 + 80 + 95) / 3 = 98.33

      expect(result?.pp).toBeCloseTo((120 + 80 + 95) / 3, 2);
    });

    it('calculates R1 correctly: (2 × PP) - periodLow', () => {
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, 1700000000),
        createSpecificCandle(110, 90, 95, 1700003600),
      ];

      const result = calculatePivotPoints(candles, 2);
      const expectedPP = (120 + 80 + 95) / 3;
      const expectedR1 = 2 * expectedPP - 80; // Use period low

      expect(result?.r1).toBeCloseTo(expectedR1, 2);
    });

    it('calculates S1 correctly: (2 × PP) - periodHigh', () => {
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, 1700000000),
        createSpecificCandle(110, 90, 95, 1700003600),
      ];

      const result = calculatePivotPoints(candles, 2);
      const expectedPP = (120 + 80 + 95) / 3;
      const expectedS1 = 2 * expectedPP - 120; // Use period high

      expect(result?.s1).toBeCloseTo(expectedS1, 2);
    });

    it('calculates R2 correctly: PP + (periodHigh - periodLow)', () => {
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, 1700000000),
        createSpecificCandle(110, 90, 95, 1700003600),
      ];

      const result = calculatePivotPoints(candles, 2);
      const expectedPP = (120 + 80 + 95) / 3;
      const expectedR2 = expectedPP + (120 - 80); // Use period range

      expect(result?.r2).toBeCloseTo(expectedR2, 2);
    });

    it('calculates S2 correctly: PP - (periodHigh - periodLow)', () => {
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, 1700000000),
        createSpecificCandle(110, 90, 95, 1700003600),
      ];

      const result = calculatePivotPoints(candles, 2);
      const expectedPP = (120 + 80 + 95) / 3;
      const expectedS2 = expectedPP - (120 - 80); // Use period range

      expect(result?.s2).toBeCloseTo(expectedS2, 2);
    });
  });

  describe('level ordering', () => {
    it('R2 > R1 > PP > S1 > S2', () => {
      const candles = createCandles(30);
      const result = calculatePivotPoints(candles, 24);

      if (result) {
        expect(result.r2).toBeGreaterThan(result.r1);
        expect(result.r1).toBeGreaterThan(result.pp);
        expect(result.pp).toBeGreaterThan(result.s1);
        expect(result.s1).toBeGreaterThan(result.s2);
      }
    });
  });

  describe('time range', () => {
    it('startTime is from first candle when periodSeconds not passed', () => {
      const candles = createCandles(30);
      const result = calculatePivotPoints(candles, 24);

      expect(result?.startTime).toBe(candles[0]?.time);
    });

    it('endTime is from last candle when periodSeconds not passed', () => {
      const candles = createCandles(30);
      const result = calculatePivotPoints(candles, 24);

      expect(result?.endTime).toBe(candles[candles.length - 1]?.time);
    });
  });

  describe('TradingView parity (periodSeconds)', () => {
    const SECONDS_PER_DAY = 86400;
    const SECONDS_PER_WEEK = 604800;

    describe('startTime must equal a real candle bar time (off-grid regression)', () => {
      // REGRESSION (pivot displacement on 1w): UNIX epoch is Thursday
      // 1970-01-01, so ``Math.floor(t / 604800) * 604800`` snaps the
      // current-period start to a Thursday. Exchange weekly candles open on
      // Monday — so the epoch-aligned Thursday is NOT a candle bar time
      // and lightweight-charts allocates a new logical-index slot for it
      // between the previous and current Monday bars (visible as a
      // "displacement" gap when Pivot Points is toggled on, most noticeable
      // on 1w because the off-grid offset is 4 days).
      //
      // Contract: ``startTime`` MUST equal one of the input candles' ``time``
      // values so it lays out on an existing logical index.
      it('1w Monday-aligned candles: startTime snaps to current Monday, NOT epoch-aligned Thursday', () => {
        // Monday 2024-05-13 00:00 UTC -> Monday 2024-05-20 00:00 UTC
        const prevMonday = 1715558400;
        const currMonday = 1716163200;
        const candles: CandlestickData[] = [
          createSpecificCandle(60_000, 55_000, 58_000, prevMonday),
          createSpecificCandle(62_000, 57_000, 60_000, currMonday),
        ];

        const result = calculatePivotPoints(candles, 2, SECONDS_PER_WEEK);

        expect(result).not.toBeNull();
        // ``Math.floor(currMonday / 604800) * 604800`` = 1715817600 (Thursday).
        // Without the snap this value would leak through and create an
        // off-grid slot. The snap must pick the first candle in the
        // current period, which is currMonday.
        expect(result!.startTime).not.toBe(1715817600);
        expect(result!.startTime).toBe(currMonday);
        expect(candles.some((c) => c.time === result!.startTime)).toBe(true);
      });

      it('intraday daily-pivot: startTime is the first candle at/after today 00:00 UTC', () => {
        // 1h chart, daily pivots: today's first 1h candle opens at 00:00 UTC.
        const startOfToday = 1716163200; // arbitrary UTC day start
        const candles: CandlestickData[] = [
          createSpecificCandle(100, 90, 95, startOfToday - 3600),
          createSpecificCandle(105, 95, 100, startOfToday),
          createSpecificCandle(110, 100, 108, startOfToday + 3600),
        ];

        const result = calculatePivotPoints(candles, 6, SECONDS_PER_DAY);

        expect(result).not.toBeNull();
        expect(result!.startTime).toBe(startOfToday);
        expect(candles.some((c) => c.time === result!.startTime)).toBe(true);
      });

      it('falls back to lastTime when no candle exists at/after the computed period start', () => {
        // Pathological: chart only has candles strictly BEFORE the computed
        // period start. ``find`` returns undefined; we must not emit an
        // off-grid time. Falling back to ``lastTime`` keeps the line endpoints
        // both on existing candle times (and ``endTime <= startTime`` then
        // routes to the empty-arrays branch in convertPivotPointsToLW).
        const candles: CandlestickData[] = [
          createSpecificCandle(120, 80, 100, 1000),
          createSpecificCandle(110, 90, 95, 2000),
        ];

        const result = calculatePivotPoints(candles, 2, 100_000);

        expect(result).not.toBeNull();
        expect(candles.some((c) => c.time === result!.startTime)).toBe(true);
      });
    });

    it('uses candles from previous completed period when periodSeconds is passed', () => {
      // Last candle "today" at 1699920000 (start of a UTC day). Previous day: 1699833600..1699920000
      const startOfPrevDay = 1699833600;
      const startOfToday = 1699920000;
      const candles: CandlestickData[] = [
        createSpecificCandle(200, 90, 150, startOfPrevDay),
        createSpecificCandle(180, 100, 120, startOfPrevDay + 3600),
        createSpecificCandle(190, 95, 110, startOfToday - 1),
        createSpecificCandle(160, 130, 140, startOfToday),
        createSpecificCandle(155, 135, 145, startOfToday + 3600),
      ];
      const result = calculatePivotPoints(candles, 6, SECONDS_PER_DAY);

      expect(result).not.toBeNull();
      // Aggregation should use previous day's H=200, L=90, close=110 (last candle of prev day)
      // PP = (200 + 90 + 110) / 3 = 133.33
      expect(result!.pp).toBeCloseTo((200 + 90 + 110) / 3, 1);
      expect(result!.r2).toBeCloseTo(result!.pp + (200 - 90), 1);
    });

    it('startTime is start of current period, endTime is last candle (line extent)', () => {
      const startOfToday = 1699920000;
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, startOfToday - SECONDS_PER_DAY),
        createSpecificCandle(110, 90, 95, startOfToday),
        createSpecificCandle(115, 85, 105, startOfToday + 7200),
      ];
      const result = calculatePivotPoints(candles, 6, SECONDS_PER_DAY);

      expect(result).not.toBeNull();
      expect(result!.startTime).toBe(startOfToday);
      expect(result!.endTime).toBe(startOfToday + 7200);
    });

    it('falls back to last N candles when no candles in previous period', () => {
      const startOfToday = 1699920000;
      const candles: CandlestickData[] = [
        createSpecificCandle(110, 90, 95, startOfToday),
        createSpecificCandle(115, 85, 100, startOfToday + 3600),
      ];
      const result = calculatePivotPoints(candles, 2, SECONDS_PER_DAY);

      expect(result).not.toBeNull();
      expect(result!.pp).toBeCloseTo((115 + 85 + 100) / 3, 1);
    });
  });

  describe('default constant', () => {
    it('DEFAULT_PIVOT_PERIOD is 24 (for hourly charts = 1 day)', () => {
      expect(DEFAULT_PIVOT_PERIOD).toBe(24);
    });
  });

  // ===========================================================================
  // calculatePivotPointsSeries — historical sequence (one pivot per period)
  // ===========================================================================
  // BEHAVIOR: high timeframes (4h/1d/1w) previously rendered ONLY the current
  // period's pivot as a short right-edge stub, because calculatePivotPoints
  // returns a single point. The series variant emits one pivot per COMPLETED
  // period (classic rule: period P's H/L/C drives the levels shown DURING the
  // next period P+1), so the chart is populated with levels across its width.
  // ===========================================================================
  describe('calculatePivotPointsSeries', () => {
    const SECONDS_PER_DAY = 86400;
    // Three consecutive UTC midnights (epoch-aligned daily buckets).
    const dayA = 1699833600;
    const dayB = dayA + SECONDS_PER_DAY;
    const dayC = dayB + SECONDS_PER_DAY;

    function threeDayIntradayCandles(): CandlestickData[] {
      return [
        // Day A: H=200, L=90, last close=110
        createSpecificCandle(200, 90, 150, dayA),
        createSpecificCandle(180, 100, 110, dayA + 3600),
        // Day B: H=160, L=120, last close=145
        createSpecificCandle(160, 130, 140, dayB),
        createSpecificCandle(155, 120, 145, dayB + 3600),
        // Day C (current, partial)
        createSpecificCandle(150, 135, 138, dayC),
        createSpecificCandle(152, 133, 149, dayC + 3600),
      ];
    }

    it('returns empty array for empty candles', () => {
      expect(calculatePivotPointsSeries([], SECONDS_PER_DAY)).toEqual([]);
    });

    it('returns empty array for non-positive periodSeconds', () => {
      const candles = threeDayIntradayCandles();

      expect(calculatePivotPointsSeries(candles, 0)).toEqual([]);
    });

    it('returns empty array when only a single completed period exists (no prior period)', () => {
      const candles: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, dayA),
        createSpecificCandle(110, 90, 95, dayA + 3600),
      ];

      expect(calculatePivotPointsSeries(candles, SECONDS_PER_DAY)).toEqual([]);
    });

    it('emits one pivot per period that has a preceding period (N buckets -> N-1 segments)', () => {
      const result = calculatePivotPointsSeries(threeDayIntradayCandles(), SECONDS_PER_DAY);

      expect(result).toHaveLength(2);
    });

    it('segment for day B uses day A H/L/C; segment for day C uses day B H/L/C', () => {
      const result = calculatePivotPointsSeries(threeDayIntradayCandles(), SECONDS_PER_DAY);

      // Segment 0 applies DURING day B, levels from day A (H=200, L=90, close=110)
      expect(result[0]!.pp).toBeCloseTo((200 + 90 + 110) / 3, 2);
      expect(result[0]!.r2).toBeCloseTo((200 + 90 + 110) / 3 + (200 - 90), 2);

      // Segment 1 applies DURING day C, levels from day B (H=160, L=120, close=145)
      expect(result[1]!.pp).toBeCloseTo((160 + 120 + 145) / 3, 2);
    });

    it('segment start/end are real candle bar times of the APPLY period', () => {
      const result = calculatePivotPointsSeries(threeDayIntradayCandles(), SECONDS_PER_DAY);

      // Segment 0 spans day B's candles
      expect(result[0]!.startTime).toBe(dayB);
      expect(result[0]!.endTime).toBe(dayB + 3600);
      // Segment 1 spans day C's candles (current period)
      expect(result[1]!.startTime).toBe(dayC);
      expect(result[1]!.endTime).toBe(dayC + 3600);
    });

    it('preserves level ordering R2 > R1 > PP > S1 > S2 in every segment', () => {
      const result = calculatePivotPointsSeries(threeDayIntradayCandles(), SECONDS_PER_DAY);

      for (const seg of result) {
        expect(seg.r2).toBeGreaterThan(seg.r1);
        expect(seg.r1).toBeGreaterThan(seg.pp);
        expect(seg.pp).toBeGreaterThan(seg.s1);
        expect(seg.s1).toBeGreaterThan(seg.s2);
      }
    });

    it('the LAST segment matches single calculatePivotPoints (current period parity)', () => {
      const candles = threeDayIntradayCandles();

      const series = calculatePivotPointsSeries(candles, SECONDS_PER_DAY);
      const single = calculatePivotPoints(candles, 2, SECONDS_PER_DAY);

      const last = series[series.length - 1]!;

      expect(last.pp).toBeCloseTo(single!.pp, 6);
      expect(last.r1).toBeCloseTo(single!.r1, 6);
      expect(last.s2).toBeCloseTo(single!.s2, 6);
    });

    it('handles single-candle periods (1d/1w semantics): one bucket per candle', () => {
      // One candle per UTC day -> each candle is its own period bucket.
      const candles: CandlestickData[] = [
        createSpecificCandle(200, 90, 110, dayA),
        createSpecificCandle(160, 120, 145, dayB),
        createSpecificCandle(150, 130, 140, dayC),
      ];

      const result = calculatePivotPointsSeries(candles, SECONDS_PER_DAY);

      expect(result).toHaveLength(2);
      // Single-candle apply period -> start == end (one bar wide)
      expect(result[0]!.startTime).toBe(dayB);
      expect(result[0]!.endTime).toBe(dayB);
      // Levels from day A's single candle
      expect(result[0]!.pp).toBeCloseTo((200 + 90 + 110) / 3, 2);
    });
  });

  describe('uses close from last candle in period', () => {
    it('close value affects PP calculation', () => {
      const candles1: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, 1700000000),
        createSpecificCandle(110, 90, 90, 1700003600), // Close = 90
      ];

      const candles2: CandlestickData[] = [
        createSpecificCandle(120, 80, 100, 1700000000),
        createSpecificCandle(110, 90, 110, 1700003600), // Close = 110 (different)
      ];

      const result1 = calculatePivotPoints(candles1, 2);
      const result2 = calculatePivotPoints(candles2, 2);

      // PP should be different because close is different
      // result1 PP = (120 + 80 + 90) / 3 = 96.67
      // result2 PP = (120 + 80 + 110) / 3 = 103.33
      expect(result1?.pp).not.toEqual(result2?.pp);
      expect(result1?.pp).toBeCloseTo(96.67, 1);
      expect(result2?.pp).toBeCloseTo(103.33, 1);
    });
  });
});
