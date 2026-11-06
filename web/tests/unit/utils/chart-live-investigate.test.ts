/**
 * @see apps/web/src/utils/chart-live-investigate.ts
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import { DEBUG_CHART_GAP_STORAGE_KEY } from '@/utils/chart-gap-debug';
import { chartLiveTrace, nextChartLiveMergeSeq } from '@/utils/chart-live-investigate';

describe('chartLiveTrace', () => {
  afterEach(() => {
    localStorage.removeItem(DEBUG_CHART_GAP_STORAGE_KEY);
  });

  it('does not log when debug flag is off', () => {
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

    chartLiveTrace('test', { x: 1 });

    expect(infoSpy).not.toHaveBeenCalled();
    infoSpy.mockRestore();
  });

  it('logs with chart-gap prefix when enabled', () => {
    localStorage.setItem(DEBUG_CHART_GAP_STORAGE_KEY, '1');
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

    chartLiveTrace('merge', { mergeSource: 'live-sync-effect' });

    expect(infoSpy).toHaveBeenCalledTimes(1);
    expect(infoSpy.mock.calls[0]?.[0]).toContain('[chart-gap]');
    infoSpy.mockRestore();
  });
});

describe('nextChartLiveMergeSeq', () => {
  it('returns increasing sequence numbers', () => {
    const a = nextChartLiveMergeSeq();
    const b = nextChartLiveMergeSeq();

    expect(b).toBe(a + 1);
  });
});
