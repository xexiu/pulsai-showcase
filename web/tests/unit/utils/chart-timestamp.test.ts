// @vitest-environment node
/**
 * Behavior tests for chart timestamp SoT (timestampToChartTime).
 *
 * Both dashboard (parseBackendCandles) and full chart (chartIndicatorsToChartData)
 * use this normalizer so chart time is Unix seconds from a single place.
 *
 * @see apps/web/src/utils/chart-timestamp.ts
 */

import { describe, expect, it } from 'vitest';

import {
  CHART_TIMESTAMP_MS_THRESHOLD,
  timestampToChartTime,
} from '../../../src/utils/chart-timestamp';

describe('CHART_TIMESTAMP_MS_THRESHOLD', () => {
  it('is 1e12 so values >= threshold are treated as milliseconds', () => {
    expect(CHART_TIMESTAMP_MS_THRESHOLD).toBe(1e12);
  });
});

describe('timestampToChartTime', () => {
  it('returns floor(ts/1000) when input number >= threshold (ms)', () => {
    const ms = 1710512100000; // 2024-03-16 15:15:00 UTC

    expect(timestampToChartTime(ms)).toBe(1710512100);
    expect(timestampToChartTime(1710512100123)).toBe(1710512100);
  });

  it('returns floor(ts) when input number < threshold and finite (seconds)', () => {
    const sec = 1710512100;

    expect(timestampToChartTime(sec)).toBe(1710512100);
    expect(timestampToChartTime(1710512100.7)).toBe(1710512100);
  });

  it('returns Unix seconds for ISO string input', () => {
    const iso = '2024-03-16T15:15:00.000Z';
    const expected = Math.floor(new Date(iso).getTime() / 1000);

    expect(timestampToChartTime(iso)).toBe(expected);
  });

  it('returns NaN for invalid string', () => {
    expect(Number.isNaN(timestampToChartTime('not-a-date'))).toBe(true);
    expect(Number.isNaN(timestampToChartTime(''))).toBe(true);
  });

  it('returns NaN for null or undefined', () => {
    expect(Number.isNaN(timestampToChartTime(null))).toBe(true);
    expect(Number.isNaN(timestampToChartTime(undefined))).toBe(true);
  });

  it('returns NaN for non-finite number', () => {
    expect(Number.isNaN(timestampToChartTime(Number.NaN))).toBe(true);
    expect(Number.isNaN(timestampToChartTime(Number.POSITIVE_INFINITY))).toBe(true);
    expect(Number.isNaN(timestampToChartTime(Number.NEGATIVE_INFINITY))).toBe(true);
  });
});
