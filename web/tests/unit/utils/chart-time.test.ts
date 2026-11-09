// @vitest-environment node
// =============================================================================
// Chart Time Utilities Tests
// =============================================================================

import { describe, expect, it } from 'vitest';

import {
  calculateCountdown,
  calculatePriceChange,
  CANDLES_PER_DAY,
  getDivergencePivotLookbackBars,
  getNextCandleClose,
  getPivotPeriodForTimeframe,
  floorUtcCandlePeriodOpenSeconds,
  getTimeframeMs,
  getTimeframeSeconds,
  TIMEFRAME_MS,
  TIMEFRAME_SEC,
} from '@/utils/chart-time';

// =============================================================================
// Tests: TIMEFRAME_MS constant
// =============================================================================

describe('TIMEFRAME_MS', () => {
  it('has correct value for 1m (60 seconds)', () => {
    expect(TIMEFRAME_MS['1m']).toBe(60 * 1000);
  });

  it('has correct value for 1h (1 hour)', () => {
    expect(TIMEFRAME_MS['1h']).toBe(60 * 60 * 1000);
  });

  it('has correct value for 4h (4 hours)', () => {
    expect(TIMEFRAME_MS['4h']).toBe(4 * 60 * 60 * 1000);
  });

  it('has correct value for 1d (24 hours)', () => {
    expect(TIMEFRAME_MS['1d']).toBe(24 * 60 * 60 * 1000);
  });

  it('has correct value for 1w (7 days)', () => {
    expect(TIMEFRAME_MS['1w']).toBe(7 * 24 * 60 * 60 * 1000);
  });

  it('has all expected timeframes', () => {
    const expectedTimeframes = [
      '1m',
      '3m',
      '5m',
      '15m',
      '30m',
      '1h',
      '2h',
      '4h',
      '6h',
      '12h',
      '1d',
      '1w',
    ];

    for (const tf of expectedTimeframes) {
      expect(TIMEFRAME_MS[tf as keyof typeof TIMEFRAME_MS]).toBeDefined();
    }
  });
});

// =============================================================================
// Tests: calculateCountdown
// =============================================================================

describe('calculateCountdown', () => {
  it('returns --:-- for invalid timeframe', () => {
    expect(calculateCountdown('invalid')).toBe('--:--');
    expect(calculateCountdown('')).toBe('--:--');
  });

  it('formats as MM:SS when less than 1 hour remaining', () => {
    // 45 minutes 30 seconds into the hour = 14:30 remaining
    const now = new Date('2024-01-01T00:45:30.000Z').getTime();
    const result = calculateCountdown('1h', now);

    expect(result).toBe('14:30');
  });

  it('formats as H:MM:SS when more than 1 hour remaining', () => {
    // 30 minutes into a 4h candle = 3:30:00 remaining
    const now = new Date('2024-01-01T00:30:00.000Z').getTime();
    const result = calculateCountdown('4h', now);

    expect(result).toBe('3:30:00');
  });

  it('pads minutes and seconds with zeros', () => {
    // 5 seconds before the hour
    const now = new Date('2024-01-01T00:59:55.000Z').getTime();
    const result = calculateCountdown('1h', now);

    expect(result).toBe('0:05');
  });

  it('handles midnight correctly for daily timeframe', () => {
    // 6pm on Jan 1 = 6 hours until next day
    const now = new Date('2024-01-01T18:00:00.000Z').getTime();
    const result = calculateCountdown('1d', now);

    expect(result).toBe('6:00:00');
  });

  it('uses current time when now is not provided', () => {
    const result = calculateCountdown('1h');

    // Should return a valid format (MM:SS or H:MM:SS)
    expect(result).toMatch(/^\d+:\d{2}(:\d{2})?$/);
  });
});

// =============================================================================
// Tests: calculatePriceChange
// =============================================================================

describe('calculatePriceChange', () => {
  it('calculates positive change correctly', () => {
    const result = calculatePriceChange(105, 100);

    expect(result.value).toBe(5);
    expect(result.isPositive).toBe(true);
  });

  it('calculates negative change correctly', () => {
    const result = calculatePriceChange(95, 100);

    expect(result.value).toBe(5);
    expect(result.isPositive).toBe(false);
  });

  it('returns zero change for same price', () => {
    const result = calculatePriceChange(100, 100);

    expect(result.value).toBe(0);
    expect(result.isPositive).toBe(true);
  });

  it('handles zero previous price (division by zero)', () => {
    const result = calculatePriceChange(100, 0);

    expect(result.value).toBe(0);
    expect(result.isPositive).toBe(true);
  });

  it('returns absolute value (always positive)', () => {
    const negativeResult = calculatePriceChange(90, 100);

    expect(negativeResult.value).toBeGreaterThanOrEqual(0);
  });

  it('calculates fractional changes correctly', () => {
    const result = calculatePriceChange(100.5, 100);

    expect(result.value).toBeCloseTo(0.5, 2);
    expect(result.isPositive).toBe(true);
  });

  it('handles large price swings', () => {
    const result = calculatePriceChange(200, 100);

    expect(result.value).toBe(100);
    expect(result.isPositive).toBe(true);
  });
});

// =============================================================================
// Tests: getNextCandleClose
// =============================================================================

describe('getNextCandleClose', () => {
  it('returns null for invalid timeframe', () => {
    expect(getNextCandleClose('invalid')).toBeNull();
  });

  it('returns next hour boundary for 1h timeframe', () => {
    const now = new Date('2024-01-01T14:30:00.000Z').getTime();
    const result = getNextCandleClose('1h', now);

    expect(result).toBe(new Date('2024-01-01T15:00:00.000Z').getTime());
  });

  it('returns next 4h boundary for 4h timeframe', () => {
    const now = new Date('2024-01-01T05:30:00.000Z').getTime();
    const result = getNextCandleClose('4h', now);

    expect(result).toBe(new Date('2024-01-01T08:00:00.000Z').getTime());
  });

  it('returns midnight for 1d timeframe', () => {
    const now = new Date('2024-01-01T18:00:00.000Z').getTime();
    const result = getNextCandleClose('1d', now);

    expect(result).toBe(new Date('2024-01-02T00:00:00.000Z').getTime());
  });
});

// =============================================================================
// Tests: getTimeframeMs
// =============================================================================

describe('getTimeframeMs', () => {
  it('returns correct milliseconds for valid timeframe', () => {
    expect(getTimeframeMs('1h')).toBe(60 * 60 * 1000);
    expect(getTimeframeMs('4h')).toBe(4 * 60 * 60 * 1000);
    expect(getTimeframeMs('1d')).toBe(24 * 60 * 60 * 1000);
  });

  it('returns null for invalid timeframe', () => {
    expect(getTimeframeMs('invalid')).toBeNull();
    expect(getTimeframeMs('')).toBeNull();
    expect(getTimeframeMs('2d')).toBeNull();
  });
});

// =============================================================================
// Tests: TIMEFRAME_SEC (SoT for period in seconds; derived once from TIMEFRAME_MS)
// =============================================================================

describe('TIMEFRAME_SEC', () => {
  it('has same keys as TIMEFRAME_MS', () => {
    const msKeys = Object.keys(TIMEFRAME_MS).sort();
    const secKeys = Object.keys(TIMEFRAME_SEC).sort();

    expect(secKeys).toEqual(msKeys);
  });

  it('equals floor(TIMEFRAME_MS/1000) for every timeframe', () => {
    const timeframes = Object.keys(TIMEFRAME_MS) as (keyof typeof TIMEFRAME_MS)[];

    for (const tf of timeframes) {
      expect(TIMEFRAME_SEC[tf]).toBe(Math.floor(TIMEFRAME_MS[tf] / 1000));
    }
  });

  it('has correct values for 1m, 1h, 1d, 1w', () => {
    expect(TIMEFRAME_SEC['1m']).toBe(60);
    expect(TIMEFRAME_SEC['1h']).toBe(3600);
    expect(TIMEFRAME_SEC['1d']).toBe(86400);
    expect(TIMEFRAME_SEC['1w']).toBe(7 * 86400);
  });
});

// =============================================================================
// Tests: floorUtcCandlePeriodOpenSeconds (BE WEEKLY_MONDAY parity)
// =============================================================================

describe('floorUtcCandlePeriodOpenSeconds', () => {
  it('floors 1w to Monday 00:00 UTC, not epoch Thursday', () => {
    const midWeekUtc = Math.floor(Date.UTC(2026, 5, 1, 18, 0, 0) / 1000);
    const mondayOpenUtc = Math.floor(Date.UTC(2026, 5, 1, 0, 0, 0) / 1000);

    expect(floorUtcCandlePeriodOpenSeconds('1w', midWeekUtc)).toBe(mondayOpenUtc);
  });

  it('floors 1h to top of hour (epoch grid)', () => {
    const utc = Math.floor(Date.UTC(2026, 5, 1, 18, 30, 0) / 1000);
    const hourOpen = Math.floor(Date.UTC(2026, 5, 1, 18, 0, 0) / 1000);

    expect(floorUtcCandlePeriodOpenSeconds('1h', utc)).toBe(hourOpen);
  });

  it('floors 3d to Binance epoch+1d grid, not pure epoch', () => {
    // Mid-bar on Binance 3d that opened 2026-08-09 00:00 UTC
    const midBarUtc = Math.floor(Date.UTC(2026, 7, 10, 12, 0, 0) / 1000);
    const binanceOpenUtc = Math.floor(Date.UTC(2026, 7, 9, 0, 0, 0) / 1000);
    const threeDaySec = 3 * 86400;
    const naiveEpoch = Math.floor(midBarUtc / threeDaySec) * threeDaySec;

    expect(naiveEpoch).not.toBe(binanceOpenUtc);
    expect(floorUtcCandlePeriodOpenSeconds('3d', midBarUtc)).toBe(binanceOpenUtc);
  });
});

// =============================================================================
// Tests: getTimeframeSeconds (lookup via TIMEFRAME_SEC; 0 for invalid)
// =============================================================================

describe('getTimeframeSeconds', () => {
  it('returns period in seconds for valid timeframe', () => {
    expect(getTimeframeSeconds('1m')).toBe(60);
    expect(getTimeframeSeconds('1h')).toBe(3600);
    expect(getTimeframeSeconds('4h')).toBe(4 * 3600);
    expect(getTimeframeSeconds('1d')).toBe(86400);
    expect(getTimeframeSeconds('1w')).toBe(7 * 86400);
  });

  it('returns 0 for invalid or unknown timeframe', () => {
    expect(getTimeframeSeconds('invalid')).toBe(0);
    expect(getTimeframeSeconds('')).toBe(0);
    expect(getTimeframeSeconds('2d')).toBe(0);
  });

  it('returns TIMEFRAME_SEC value for known timeframes', () => {
    const timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w'] as const;

    for (const tf of timeframes) {
      expect(getTimeframeSeconds(tf)).toBe(TIMEFRAME_SEC[tf as keyof typeof TIMEFRAME_SEC]);
    }
  });
});

// =============================================================================
// Tests: CANDLES_PER_DAY and getPivotPeriodForTimeframe - BEHAVIOR TESTS
// =============================================================================
//
// CRITICAL BEHAVIOR:
// All timeframes should produce pivot periods that represent exactly 1 DAY.
// This ensures a 15m trader and 4h trader see IDENTICAL pivot levels.
//
// The value tests below verify the MATH is correct, but the key behavior test
// is "period × candleLength = 24 hours" for all timeframes.
// =============================================================================

describe('CANDLES_PER_DAY', () => {
  // ===========================================================================
  // BEHAVIOR TEST: All timeframes represent exactly 1 day
  // ===========================================================================
  describe('core behavior: period × candle duration = 24 hours', () => {
    it('all intraday timeframes produce exactly 24 hours of coverage', () => {
      // WHY THIS IS THE CRITICAL TEST:
      // This ensures a 15m trader and 4h trader see the SAME pivot levels
      // because both are looking at the SAME 24-hour period

      const intradayTimeframes = ['15m', '30m', '1h', '2h', '4h', '6h', '12h'] as const;
      const MINUTES_PER_DAY = 24 * 60; // 1440 minutes

      for (const tf of intradayTimeframes) {
        const candlesPerDay = CANDLES_PER_DAY[tf];
        const candleMinutes = TIMEFRAME_MS[tf] / (60 * 1000);
        const totalMinutes = candlesPerDay * candleMinutes;

        // BEHAVIOR: period × duration MUST equal 24 hours
        expect(totalMinutes).toBe(MINUTES_PER_DAY);
      }
    });

    it('1m, 3m, 5m timeframes also produce 24 hours', () => {
      // Scalper timeframes should also represent 1 day
      const scalperTimeframes = ['1m', '3m', '5m'] as const;
      const MINUTES_PER_DAY = 24 * 60;

      for (const tf of scalperTimeframes) {
        const candlesPerDay = CANDLES_PER_DAY[tf];
        const candleMinutes = TIMEFRAME_MS[tf] / (60 * 1000);
        const totalMinutes = candlesPerDay * candleMinutes;

        expect(totalMinutes).toBe(MINUTES_PER_DAY);
      }
    });
  });

  // ===========================================================================
  // Value verification (ensures no typos in constants)
  // ===========================================================================
  describe('value verification', () => {
    it('1h has 24 candles per day (baseline)', () => {
      expect(CANDLES_PER_DAY['1h']).toBe(24);
    });

    it('15m has 4x more candles than 1h (4 per hour)', () => {
      expect(CANDLES_PER_DAY['15m']).toBe(CANDLES_PER_DAY['1h'] * 4);
    });

    it('4h has 1/4 the candles of 1h (6 per day)', () => {
      expect(CANDLES_PER_DAY['4h']).toBe(CANDLES_PER_DAY['1h'] / 4);
    });

    it('1d is exactly 1 candle', () => {
      expect(CANDLES_PER_DAY['1d']).toBe(1);
    });

    it('3d is 1 candle for daily-pivot methodology', () => {
      expect(CANDLES_PER_DAY['3d']).toBe(1);
    });

    it('1w uses 5 trading days (not 7)', () => {
      // WHY 5? Weekly pivots traditionally use 5 trading days
      expect(CANDLES_PER_DAY['1w']).toBe(5);
    });
  });

  it('has all expected timeframes defined', () => {
    const expectedTimeframes = [
      '1m',
      '3m',
      '5m',
      '15m',
      '30m',
      '1h',
      '2h',
      '4h',
      '6h',
      '8h',
      '12h',
      '1d',
      '3d',
      '1w',
    ];

    for (const tf of expectedTimeframes) {
      expect(CANDLES_PER_DAY[tf as keyof typeof CANDLES_PER_DAY]).toBeDefined();
    }
  });
});

describe('getPivotPeriodForTimeframe', () => {
  // ===========================================================================
  // BEHAVIOR TEST: Function returns periods that produce 24-hour coverage
  // ===========================================================================
  describe('core behavior: returned period produces 24-hour coverage', () => {
    it('returns period that covers exactly 24 hours for all intraday timeframes', () => {
      const intradayTimeframes = ['15m', '30m', '1h', '2h', '4h', '6h', '12h'] as const;
      const MINUTES_PER_DAY = 24 * 60;

      for (const tf of intradayTimeframes) {
        const period = getPivotPeriodForTimeframe(tf);
        const candleMinutes = TIMEFRAME_MS[tf] / (60 * 1000);
        const totalMinutes = period * candleMinutes;

        // BEHAVIOR: returned period × duration MUST equal 24 hours
        expect(totalMinutes).toBe(MINUTES_PER_DAY);
      }
    });
  });

  // ===========================================================================
  // Edge cases
  // ===========================================================================
  describe('edge cases', () => {
    it('returns safe default (24) for invalid timeframe', () => {
      // BEHAVIOR: Invalid input should not crash, return safe default
      expect(getPivotPeriodForTimeframe('invalid')).toBe(24);
      expect(getPivotPeriodForTimeframe('')).toBe(24);
      expect(getPivotPeriodForTimeframe('2d')).toBe(24);
    });

    it('handles daily timeframe correctly', () => {
      // 1d uses previous day's single candle
      expect(getPivotPeriodForTimeframe('1d')).toBe(1);
    });

    it('handles weekly timeframe correctly', () => {
      // 1w uses 5 trading days
      expect(getPivotPeriodForTimeframe('1w')).toBe(5);
    });
  });

  // ===========================================================================
  // Return value verification (sanity checks)
  // ===========================================================================
  describe('return values', () => {
    it('returns 96 for 15m', () => {
      expect(getPivotPeriodForTimeframe('15m')).toBe(96);
    });

    it('returns 24 for 1h', () => {
      expect(getPivotPeriodForTimeframe('1h')).toBe(24);
    });

    it('returns 6 for 4h', () => {
      expect(getPivotPeriodForTimeframe('4h')).toBe(6);
    });
  });
});

// =============================================================================
// Tests: getDivergencePivotLookbackBars - BEHAVIOR TESTS
// =============================================================================
//
// A divergence pivot must be strictly beyond this many bars on EACH side, so it is also the
// pivot's confirmation lag. Mirrors BE chart_divergence_params.pivot_lookback_bars_for_timeframe.
// =============================================================================

describe('getDivergencePivotLookbackBars', () => {
  it('never shrinks as the timeframe grows (LTF confirms fast, HTF filters noise)', () => {
    const ordered = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w'];
    const lookbacks = ordered.map((tf) => getDivergencePivotLookbackBars(tf));

    for (let i = 1; i < lookbacks.length; i++) {
      expect(lookbacks[i]).toBeGreaterThanOrEqual(lookbacks[i - 1]!);
    }
  });

  it.each([
    ['5m', 2],
    ['15m', 2],
    ['1h', 3],
    ['4h', 4],
    ['6h', 4],
    ['1d', 5],
  ])('%s pivots are %i bars on each side', (timeframe, bars) => {
    expect(getDivergencePivotLookbackBars(timeframe)).toBe(bars);
  });

  it('falls back to the 1h value for an unknown or empty timeframe', () => {
    expect(getDivergencePivotLookbackBars('invalid')).toBe(getDivergencePivotLookbackBars('1h'));
    expect(getDivergencePivotLookbackBars('')).toBe(getDivergencePivotLookbackBars('1h'));
  });

  it('does not treat inherited object keys as timeframes', () => {
    expect(getDivergencePivotLookbackBars('toString')).toBe(getDivergencePivotLookbackBars('1h'));
  });
});
