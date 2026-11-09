// @vitest-environment node

import { describe, expect, it } from 'vitest';

import { resolveEmbeddedDashboardChartPeerPrefetchTimeframes } from '@/hooks/resolveEmbeddedDashboardChartPeerPrefetchTimeframes';
import type { Timeframe } from '@/types/chart';

const ALL: Timeframe[] = ['15m', '1h', '4h', '1d'];

describe('resolveEmbeddedDashboardChartPeerPrefetchTimeframes', () => {
  it('returns all allowed timeframes when disabled list is omitted', () => {
    expect(resolveEmbeddedDashboardChartPeerPrefetchTimeframes(ALL)).toEqual(ALL);
  });

  it('returns all allowed timeframes when disabled list is empty', () => {
    expect(resolveEmbeddedDashboardChartPeerPrefetchTimeframes(ALL, [])).toEqual(ALL);
  });

  it('excludes tier-disabled timeframes for dashboard peer warm', () => {
    expect(resolveEmbeddedDashboardChartPeerPrefetchTimeframes(ALL, ['4h', '1d'])).toEqual([
      '15m',
      '1h',
    ]);
  });
});
