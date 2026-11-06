/**
 * @see apps/web/src/utils/chart-gap-debug.ts
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  analyzeBarTimes,
  chartGapLog,
  chartGapWarn,
  DEBUG_CHART_GAP_STORAGE_KEY,
  isChartGapDebugEnabled,
  logOhlcvApiGapCheck,
  resolveSetDataGapHint,
  tailTimes,
  type ChartGapCulprit,
} from '@/utils/chart-gap-debug';

describe('isChartGapDebugEnabled', () => {
  afterEach(() => {
    localStorage.removeItem(DEBUG_CHART_GAP_STORAGE_KEY);
  });

  it('is false by default', () => {
    expect(isChartGapDebugEnabled()).toBe(false);
  });

  it('is true when DEBUG_CHART_GAP is set', () => {
    localStorage.setItem(DEBUG_CHART_GAP_STORAGE_KEY, '1');

    expect(isChartGapDebugEnabled()).toBe(true);
  });
});

describe('analyzeBarTimes', () => {
  const period = 300;

  it('reports no time gaps for consecutive 5m bars', () => {
    const times = [1000, 1300, 1600, 1900];

    expect(analyzeBarTimes(times, period).timeGapCount).toBe(0);
  });

  it('detects a missing bar (delta > period)', () => {
    const times = [1000, 1300, 1900];

    const result = analyzeBarTimes(times, period);

    expect(result.timeGapCount).toBe(1);
    expect(result.timeGaps[0]).toMatchObject({
      index: 2,
      prevTime: 1300,
      time: 1900,
      deltaSec: 600,
      expectedDeltaSec: 300,
    });
  });

  it('counts duplicate timestamps', () => {
    const result = analyzeBarTimes([1000, 1300, 1300, 1600], period);

    expect(result.duplicateTimeCount).toBe(1);
  });

  it('flags large open vs previous close as price discontinuity', () => {
    const times = [1000, 1300];
    const ohlc = [
      { open: 100, close: 100 },
      { open: 102, close: 102 },
    ];

    const result = analyzeBarTimes(times, period, ohlc);

    expect(result.priceDiscontinuityCount).toBe(1);
    expect(result.priceDiscontinuities[0]?.pctMove).toBe(2);
  });
});

describe('chartGapLog', () => {
  afterEach(() => {
    localStorage.removeItem(DEBUG_CHART_GAP_STORAGE_KEY);
  });

  it('does not log when opt-in flag is off', () => {
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

    chartGapLog('test', { foo: 1 });

    expect(infoSpy).not.toHaveBeenCalled();
    infoSpy.mockRestore();
  });

  it('writes to console when enabled', () => {
    localStorage.setItem(DEBUG_CHART_GAP_STORAGE_KEY, '1');
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

    chartGapLog('probe', { bar: 1 });

    expect(infoSpy).toHaveBeenCalledTimes(1);
    expect(infoSpy.mock.calls[0]?.[0]).toContain('[chart-gap]');
    infoSpy.mockRestore();
  });
});

/**
 * The verdict→hint mapping and the remaining emitters.
 *
 * WHY (measured 2026-08-29): chart-gap-debug.ts carried 33 uncovered branches, the third-largest
 * branch deficit in the FE report while the gate failed at 83.92% branches against an 85%
 * threshold. `resolveSetDataGapCulprit` already has its own file
 * (chart-gap-debug-setdata-verdict.test.ts), and the price-discontinuity path is covered above;
 * what nothing exercised was the HINT each culprit maps to, the warn emitter, the API-gap
 * verdict, and `tailTimes`.
 *
 * The hint matters because it is the sentence a developer reads at 2am to decide whether a chart
 * hole is a backend timestamp gap or an FE display-mapping artifact. A wrong hint sends the
 * investigation to the wrong repo.
 */
describe('resolveSetDataGapHint — every culprit names where to look', () => {
  it.each([
    ['BE_OHLCV_TIMESTAMP_GAPS', 'investigate_chart_gaps.py'],
    ['FE_DISPLAY_MAPPING_GAPS', 'display holes'],
    ['FE_PREP_DEDUPED_BARS', 'duplicate display times'],
    ['FE_LWC_SERIES_GAPS', 'lightweight-charts'],
    ['FE_PREP_DROPPED_BARS', 'dropped invalid OHLC'],
  ])('%s points at %s', (culprit, needle) => {
    expect(resolveSetDataGapHint(culprit as ChartGapCulprit)).toContain(needle);
  });

  it('falls through to the live-merge hint for the OK verdict', () => {
    expect(resolveSetDataGapHint('OK_NO_GAP_IN_DATA')).toContain('live merge');
  });

  it('falls through for the live-merge suspect, which has no bespoke hint', () => {
    // FE_LIVE_MERGE_SUSPECT is a declared culprit with no branch of its own — it lands on the
    // same default as OK_NO_GAP_IN_DATA. Pinned so a future bespoke hint is a deliberate change.
    expect(resolveSetDataGapHint('FE_LIVE_MERGE_SUSPECT')).toContain('live merge');
  });
});

describe('tailTimes', () => {
  it('returns a copy when the series is already short', () => {
    const times = [1, 2, 3];
    const tail = tailTimes(times);

    expect(tail).toEqual(times);
    expect(tail).not.toBe(times);
  });

  it('keeps only the last bars for a long series', () => {
    expect(tailTimes([1, 2, 3, 4, 5, 6, 7, 8, 9])).toEqual([4, 5, 6, 7, 8, 9]);
  });
});

describe('chartGapWarn / logOhlcvApiGapCheck — silent unless opted in', () => {
  afterEach(() => {
    localStorage.removeItem(DEBUG_CHART_GAP_STORAGE_KEY);
    vi.restoreAllMocks();
  });

  it('warns nothing while the debug flag is off', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    chartGapWarn('anything', { a: 1 });

    expect(warn).not.toHaveBeenCalled();
  });

  it('warns once the flag is on', () => {
    localStorage.setItem(DEBUG_CHART_GAP_STORAGE_KEY, '1');
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    chartGapWarn('verdict', { culprit: 'x' });

    expect(warn).toHaveBeenCalledTimes(1);
  });

  it('emits nothing from logOhlcvApiGapCheck while the flag is off', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const info = vi.spyOn(console, 'info').mockImplementation(() => {});

    logOhlcvApiGapCheck({
      symbol: 'BTCUSDT',
      timeframe: '4h',
      consumer: 'dashboard',
      isPlaceholderData: false,
      candleCount: 2,
      utcBarTimes: [14400, 28800],
    });

    expect(warn).not.toHaveBeenCalled();
    expect(info).not.toHaveBeenCalled();
  });

  it('blames the backend when the API timestamps themselves have a hole', () => {
    localStorage.setItem(DEBUG_CHART_GAP_STORAGE_KEY, '1');
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    vi.spyOn(console, 'info').mockImplementation(() => {});
    logOhlcvApiGapCheck({
      symbol: 'BTCUSDT',
      timeframe: '4h',
      consumer: 'dashboard',
      isPlaceholderData: false,
      // 4h = 14400s; the third bar is two periods late, so the series has a hole.
      candleCount: 3,
      utcBarTimes: [14400, 28800, 72000],
    });

    const payload = warn.mock.calls[0]?.[1] as Record<string, unknown>;

    expect(payload['culprit']).toBe('BE_OHLCV_TIMESTAMP_GAPS');
    expect(payload['beIsCulprit']).toBe(true);
  });

  it('clears the backend when the API series is contiguous', () => {
    localStorage.setItem(DEBUG_CHART_GAP_STORAGE_KEY, '1');
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    vi.spyOn(console, 'info').mockImplementation(() => {});
    logOhlcvApiGapCheck({
      symbol: 'BTCUSDT',
      timeframe: '4h',
      consumer: 'dashboard',
      isPlaceholderData: true,
      candleCount: 3,
      utcBarTimes: [14400, 28800, 43200],
    });

    const payload = warn.mock.calls[0]?.[1] as Record<string, unknown>;

    expect(payload['culprit']).toBe('OK_NO_GAP_IN_DATA');
    expect(payload['beIsCulprit']).toBe(false);
  });
});

describe('analyzeBarTimes — the guards that stop a bad series poisoning the verdict', () => {
  it('reports no discontinuity when the ohlc length does not match the times', () => {
    const result = analyzeBarTimes([14400, 28800, 43200], 14400, [{ open: 1, close: 1 }]);

    expect(result.priceDiscontinuityCount).toBe(0);
  });

  it('survives a zero previous close instead of dividing by it', () => {
    const result = analyzeBarTimes([14400, 28800], 14400, [
      { open: 0, close: 0 },
      { open: 1, close: 1 },
    ]);

    expect(Number.isFinite(result.priceDiscontinuities[0]?.pctMove ?? 0)).toBe(true);
  });

  it('counts a non-ascending time apart from a duplicate', () => {
    const result = analyzeBarTimes([100, 100, 50], 10);

    expect(result.duplicateTimeCount).toBe(1);
    expect(result.nonAscendingCount).toBe(1);
  });

  it('drops non-finite and non-positive times before analysing', () => {
    expect(analyzeBarTimes([Number.NaN, -5, 0, 100], 10).barCount).toBe(1);
  });

  it('reports no gap when the period is unknown', () => {
    // periodSec <= 0 disables gap detection rather than flagging every bar as a hole.
    expect(analyzeBarTimes([100, 999999], 0).timeGapCount).toBe(0);
  });
});
