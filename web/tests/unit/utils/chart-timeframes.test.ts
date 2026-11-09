// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { getResolvedChartTimeframes } from '@/utils/chart-timeframes';

describe('getResolvedChartTimeframes', () => {
  it('returns prop when non-empty', () => {
    const prop = ['1h', '4h'] as const;

    expect(getResolvedChartTimeframes([...prop])).toEqual(['1h', '4h']);
  });

  it('returns shared fallback when prop is undefined', () => {
    const result = getResolvedChartTimeframes(undefined);

    expect(result).toContain('5m');
    expect(result).toContain('1h');
    expect(result).toContain('1w');
    expect(result.length).toBeGreaterThan(0);
  });

  it('returns shared fallback when prop is null', () => {
    const result = getResolvedChartTimeframes(null);

    expect(result).toContain('1h');
    expect(result.length).toBeGreaterThan(0);
  });

  it('returns shared fallback when prop is empty array', () => {
    const result = getResolvedChartTimeframes([]);

    expect(result).toContain('1h');
    expect(result.length).toBeGreaterThan(0);
  });
});
