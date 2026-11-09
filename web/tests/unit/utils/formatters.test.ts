// @vitest-environment node
// =============================================================================
// Formatters Utility Tests
// =============================================================================
//
// WHY THESE TESTS?
// - formatPrice: Currency formatting with edge cases
// - formatPercent: Sign handling, decimal precision
// - formatTime: Null handling, time format
// - formatCompact: Large number abbreviation boundaries
// =============================================================================

import { describe, expect, it } from 'vitest';

import {
  formatChartTooltipTime,
  formatCompact,
  formatCryptoPrice,
  formatDelta,
  formatMetricValue,
  formatParam,
  formatPercent,
  formatPrice,
  formatRatioPercent,
  formatRatioPercent2,
  formatTime,
  formatUsd,
  formatUsd2,
  formatVolume,
  isPositiveNumber,
  safeFormatNumber,
  safeFormatPercent,
  safeFormatUsd,
} from '@/utils/formatters';

describe('formatters', () => {
  // ===========================================================================
  // formatPrice
  // ===========================================================================
  describe('formatPrice', () => {
    it('formats positive number with default currency', () => {
      expect(formatPrice(1234.56)).toBe('$1,234.56');
    });

    it('formats with custom currency symbol', () => {
      expect(formatPrice(1234.56, '€')).toBe('€1,234.56');
    });

    it('formats with custom decimal places', () => {
      expect(formatPrice(1234.567, '$', 3)).toBe('$1,234.567');
    });

    it('formats zero', () => {
      expect(formatPrice(0)).toBe('$0.00');
    });

    it('formats small decimals', () => {
      expect(formatPrice(0.01)).toBe('$0.01');
    });

    it('formats large numbers with commas', () => {
      expect(formatPrice(1000000)).toBe('$1,000,000.00');
    });

    it('rounds correctly when decimals exceed precision', () => {
      expect(formatPrice(99.999, '$', 2)).toBe('$100.00');
    });
  });

  // ===========================================================================
  // formatPercent
  // ===========================================================================
  describe('formatPercent', () => {
    it('formats positive percentage with + sign', () => {
      expect(formatPercent(5.5)).toBe('+5.50%');
    });

    it('formats negative percentage with - sign', () => {
      expect(formatPercent(-3.2)).toBe('-3.20%');
    });

    it('formats zero with + sign', () => {
      expect(formatPercent(0)).toBe('+0.00%');
    });

    it('formats with custom decimal places', () => {
      expect(formatPercent(5.567, 1)).toBe('+5.6%');
    });

    it('formats without sign when showSign is false', () => {
      expect(formatPercent(5.5, 2, false)).toBe('5.50%');
      expect(formatPercent(-5.5, 2, false)).toBe('-5.50%');
    });
  });

  // ===========================================================================
  // formatTime
  // ===========================================================================
  describe('formatTime', () => {
    it('returns dashes for null date', () => {
      expect(formatTime(null)).toBe('--:--:--');
    });

    it('formats date to locale time string', () => {
      const date = new Date('2026-01-26T14:30:25');
      const result = formatTime(date);

      // Should contain time components (locale-dependent format)
      expect(result).toContain(':');
    });
  });

  // ===========================================================================
  // formatCompact
  // ===========================================================================
  describe('formatCompact', () => {
    it('returns number as string for values under 1000', () => {
      expect(formatCompact(999)).toBe('999');
      expect(formatCompact(0)).toBe('0');
    });

    it('formats thousands with K suffix', () => {
      expect(formatCompact(1000)).toBe('1.0K');
      expect(formatCompact(1500)).toBe('1.5K');
      expect(formatCompact(999999)).toBe('1000.0K');
    });

    it('formats millions with M suffix', () => {
      expect(formatCompact(1000000)).toBe('1.0M');
      expect(formatCompact(1500000)).toBe('1.5M');
      expect(formatCompact(999999999)).toBe('1000.0M');
    });

    it('formats billions with B suffix', () => {
      expect(formatCompact(1000000000)).toBe('1.0B');
      expect(formatCompact(1500000000)).toBe('1.5B');
    });

    // Edge cases
    it('handles boundary values correctly', () => {
      expect(formatCompact(999)).toBe('999');
      expect(formatCompact(1000)).toBe('1.0K');
      expect(formatCompact(999999)).toBe('1000.0K');
      expect(formatCompact(1000000)).toBe('1.0M');
    });
  });

  // ===========================================================================
  // formatRatioPercent (ML metrics)
  // ===========================================================================
  describe('formatRatioPercent', () => {
    it('converts ratio to percentage with 1 decimal', () => {
      expect(formatRatioPercent(0.856)).toBe('85.6%');
    });

    it('handles 0', () => {
      expect(formatRatioPercent(0)).toBe('0.0%');
    });

    it('handles 1', () => {
      expect(formatRatioPercent(1)).toBe('100.0%');
    });

    it('rounds correctly', () => {
      // Note: JavaScript toFixed uses banker's rounding for .5 cases
      expect(formatRatioPercent(0.8556)).toBe('85.6%');
      expect(formatRatioPercent(0.8554)).toBe('85.5%');
    });
  });

  // ===========================================================================
  // formatRatioPercent2 (ML metrics precise)
  // ===========================================================================
  describe('formatRatioPercent2', () => {
    it('converts ratio to percentage with 2 decimals', () => {
      expect(formatRatioPercent2(0.0856)).toBe('8.56%');
    });

    it('handles small values', () => {
      expect(formatRatioPercent2(0.0001)).toBe('0.01%');
    });

    it('handles negative values (drawdown)', () => {
      expect(formatRatioPercent2(-0.15)).toBe('-15.00%');
    });
  });

  // ===========================================================================
  // formatUsd
  // ===========================================================================
  describe('formatUsd', () => {
    it('formats with dollar sign and commas', () => {
      expect(formatUsd(10000)).toBe('$10,000');
    });

    it('handles zero', () => {
      expect(formatUsd(0)).toBe('$0');
    });

    it('handles large numbers', () => {
      expect(formatUsd(1000000)).toBe('$1,000,000');
    });
  });

  // ===========================================================================
  // formatUsd2
  // ===========================================================================
  describe('formatUsd2', () => {
    it('formats with 2 decimal places', () => {
      expect(formatUsd2(123.456)).toBe('$123.46');
    });

    it('handles negative values (P&L)', () => {
      expect(formatUsd2(-50.5)).toBe('$-50.50');
    });

    it('handles zero', () => {
      expect(formatUsd2(0)).toBe('$0.00');
    });
  });

  // ===========================================================================
  // formatParam
  // ===========================================================================
  describe('formatParam', () => {
    it('formats numbers with 4 decimals', () => {
      expect(formatParam(0.01234567)).toBe('0.0123');
    });

    it('handles integers', () => {
      expect(formatParam(5)).toBe('5.0000');
    });

    it('passes through strings', () => {
      expect(formatParam('gbtree')).toBe('gbtree');
    });

    it('converts booleans to string', () => {
      expect(formatParam(true)).toBe('true');
    });
  });

  // ===========================================================================
  // formatDelta
  // ===========================================================================
  describe('formatDelta', () => {
    it('formats positive delta with + sign for percentage', () => {
      expect(formatDelta(0.05, true)).toBe('+5.00%');
    });

    it('formats negative delta for percentage', () => {
      expect(formatDelta(-0.02, true)).toBe('-2.00%');
    });

    it('formats positive delta for non-percentage', () => {
      expect(formatDelta(0.001, false)).toBe('+0.0010');
    });

    it('formats zero with + sign', () => {
      expect(formatDelta(0, true)).toBe('+0.00%');
    });
  });

  // ===========================================================================
  // formatMetricValue
  // ===========================================================================
  describe('formatMetricValue', () => {
    it('formats as percentage when isPercentage is true', () => {
      expect(formatMetricValue(0.85, true)).toBe('85.00%');
    });

    it('formats with 4 decimals when isPercentage is false', () => {
      expect(formatMetricValue(1.5, false)).toBe('1.5000');
    });

    it('handles edge values', () => {
      expect(formatMetricValue(0, true)).toBe('0.00%');
      expect(formatMetricValue(1, true)).toBe('100.00%');
    });
  });

  // ===========================================================================
  // formatCryptoPrice (Chart Legend)
  // ===========================================================================
  describe('formatCryptoPrice', () => {
    it('formats large prices (>= 1000) with 2 decimals and commas', () => {
      expect(formatCryptoPrice(88319.35)).toBe('88,319.35');
      expect(formatCryptoPrice(1000)).toBe('1,000.00');
    });

    it('formats medium prices (1-999) with 4 decimals', () => {
      expect(formatCryptoPrice(123.4567)).toBe('123.4567');
      expect(formatCryptoPrice(1)).toBe('1.0000');
      expect(formatCryptoPrice(999.9999)).toBe('999.9999');
    });

    it('formats small prices (< 1) with 8 decimals', () => {
      expect(formatCryptoPrice(0.12345678)).toBe('0.12345678');
      expect(formatCryptoPrice(0.00000123)).toBe('0.00000123');
    });

    it('handles zero', () => {
      expect(formatCryptoPrice(0)).toBe('0.00000000');
    });

    it('handles typical BTC price', () => {
      const result = formatCryptoPrice(88456.78);

      expect(result).toBe('88,456.78');
    });

    it('handles typical ETH price', () => {
      const result = formatCryptoPrice(3456.7891);

      expect(result).toBe('3,456.79');
    });

    it('handles typical shitcoin price', () => {
      const result = formatCryptoPrice(0.000000042);

      expect(result).toBe('0.00000004');
    });
  });

  // ===========================================================================
  // formatVolume (Chart Legend)
  // ===========================================================================
  describe('formatVolume', () => {
    it('formats billions with B suffix and 2 decimals', () => {
      expect(formatVolume(1_234_567_890)).toBe('1.23B');
      expect(formatVolume(1_000_000_000)).toBe('1.00B');
    });

    it('formats millions with M suffix and 2 decimals', () => {
      expect(formatVolume(1_234_567)).toBe('1.23M');
      expect(formatVolume(1_000_000)).toBe('1.00M');
    });

    it('formats thousands with K suffix and 2 decimals', () => {
      expect(formatVolume(1_234)).toBe('1.23K');
      expect(formatVolume(1_000)).toBe('1.00K');
    });

    it('formats small values with 2 decimals (no suffix)', () => {
      expect(formatVolume(123)).toBe('123.00');
      expect(formatVolume(0)).toBe('0.00');
    });

    it('uses 2 decimals (more precise than formatCompact)', () => {
      // formatVolume uses 2 decimals, formatCompact uses 1
      expect(formatVolume(1_234_567)).toBe('1.23M');
      expect(formatCompact(1_234_567)).toBe('1.2M');
    });

    it('handles typical crypto volume', () => {
      // BTC daily volume ~ $20-50B
      expect(formatVolume(25_000_000_000)).toBe('25.00B');
      // ETH daily volume ~ $10-20B
      expect(formatVolume(15_000_000_000)).toBe('15.00B');
    });
  });

  // ===========================================================================
  // Safe Formatters - Handle unknown/null input (Sprint 2.3b)
  // ===========================================================================

  describe('safeFormatPercent', () => {
    it('formats valid number as percentage', () => {
      expect(safeFormatPercent(0.1234)).toBe('12.34%');
      expect(safeFormatPercent(0)).toBe('0.00%');
      expect(safeFormatPercent(-0.05)).toBe('-5.00%');
    });

    it('returns fallback for non-numeric values', () => {
      expect(safeFormatPercent(null)).toBe('-');
      expect(safeFormatPercent(undefined)).toBe('-');
      expect(safeFormatPercent('string')).toBe('-');
      expect(safeFormatPercent({})).toBe('-');
    });

    it('uses custom fallback', () => {
      expect(safeFormatPercent(null, 'N/A')).toBe('N/A');
    });
  });

  describe('safeFormatNumber', () => {
    it('formats valid number with decimals', () => {
      expect(safeFormatNumber(123.456)).toBe('123.46');
      expect(safeFormatNumber(123.456, 1)).toBe('123.5');
      expect(safeFormatNumber(123.456, 0)).toBe('123');
    });

    it('returns fallback for non-numeric values', () => {
      expect(safeFormatNumber(null)).toBe('-');
      expect(safeFormatNumber(undefined)).toBe('-');
      expect(safeFormatNumber('not a number')).toBe('-');
    });

    it('uses custom fallback', () => {
      expect(safeFormatNumber(null, 2, '---')).toBe('---');
    });
  });

  describe('safeFormatUsd', () => {
    it('formats valid number as USD', () => {
      expect(safeFormatUsd(1234.56)).toBe('$1234.56');
      expect(safeFormatUsd(0)).toBe('$0.00');
    });

    it('returns fallback for non-numeric values', () => {
      expect(safeFormatUsd(null)).toBe('-');
      expect(safeFormatUsd(undefined)).toBe('-');
    });
  });

  describe('isPositiveNumber', () => {
    it('returns true for positive numbers', () => {
      expect(isPositiveNumber(1)).toBe(true);
      expect(isPositiveNumber(0.001)).toBe(true);
      expect(isPositiveNumber(1000000)).toBe(true);
    });

    it('returns false for zero and negative numbers', () => {
      expect(isPositiveNumber(0)).toBe(false);
      expect(isPositiveNumber(-1)).toBe(false);
      expect(isPositiveNumber(-0.001)).toBe(false);
    });

    it('returns false for non-numeric values', () => {
      expect(isPositiveNumber(null)).toBe(false);
      expect(isPositiveNumber(undefined)).toBe(false);
      expect(isPositiveNumber('5')).toBe(false);
      expect(isPositiveNumber({})).toBe(false);
    });
  });

  describe('formatChartTooltipTime', () => {
    // 1773675900 = 2026-03-16T15:45:00.000Z (15:45 UTC). Europe/Madrid = UTC+1 → 16:45.
    const unixSec15_45UTC = 1773675900;

    it('formats in UTC when timeZone is UTC', () => {
      const result = formatChartTooltipTime(unixSec15_45UTC, 'UTC');

      expect(result).toMatch(/15:45/);
      expect(result).toContain('(+0)');
    });

    it('formats in Europe/Madrid so 15:45 UTC shows as 16:45 local (regression: -1h bug)', () => {
      const result = formatChartTooltipTime(unixSec15_45UTC, 'Europe/Madrid');

      expect(result).toMatch(/16:45/);
      expect(result).toContain('(+1)');
    });

    it('applies timezone so UTC and Europe/Madrid differ', () => {
      const utc = formatChartTooltipTime(unixSec15_45UTC, 'UTC');
      const madrid = formatChartTooltipTime(unixSec15_45UTC, 'Europe/Madrid');

      expect(utc).not.toBe(madrid);
    });

    it('uses offsetTimeZone for (+N) when wall clock is formatted as UTC (LWC timeToTz)', () => {
      const utcWall = formatChartTooltipTime(unixSec15_45UTC, 'UTC');
      const utcWallMadridOffset = formatChartTooltipTime(unixSec15_45UTC, 'UTC', {
        offsetTimeZone: 'Europe/Madrid',
      });

      expect(utcWall).toContain('(+0)');
      expect(utcWallMadridOffset).toMatch(/15:45/);
      expect(utcWallMadridOffset).toContain('(+1)');
      expect(utcWallMadridOffset).not.toContain('(+0)');
    });

    it('for local-as-UTC bar time, UTC yields bar label; other zone yields wrong hour (display contract)', () => {
      const utcLabel = formatChartTooltipTime(unixSec15_45UTC, 'UTC');
      const madridLabel = formatChartTooltipTime(unixSec15_45UTC, 'Europe/Madrid');

      expect(utcLabel).toMatch(/15:45/);
      expect(madridLabel).toMatch(/16:45/);
      expect(utcLabel).not.toBe(madridLabel);
    });

    it('without timeZone uses runtime default (toLocaleString)', () => {
      const result = formatChartTooltipTime(unixSec15_45UTC);

      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });
  });
});
