// @vitest-environment node
/**
 * Regression: legacy timeToTz on 5m bars must keep +300s on the display axis (no LWC holes).
 */

import { describe, expect, it } from 'vitest';

import { analyzeBarTimes } from '@/utils/chart-gap-debug';
import { mapUtcBarOpenSecondsForChartDisplay } from '@/utils/chart-timezone';

describe('mapUtcBarOpenSecondsForChartDisplay 5m steps (Europe/Madrid)', () => {
  const timezone = 'Europe/Madrid';
  const timeframe = '5m';
  const periodSec = 300;

  it('keeps 300s display deltas for May 25 2026 morning (09:00–10:00 local)', () => {
    const startUtc = Math.floor(Date.UTC(2026, 4, 25, 6, 0, 0) / 1000);
    const utcTimes: number[] = [];
    const displayTimes: number[] = [];

    for (let i = 0; i < 48; i += 1) {
      const utc = startUtc + i * periodSec;

      utcTimes.push(utc);
      displayTimes.push(mapUtcBarOpenSecondsForChartDisplay(utc, timezone, timeframe));
    }

    expect(analyzeBarTimes(utcTimes, periodSec).timeGapCount).toBe(0);
    expect(analyzeBarTimes(displayTimes, periodSec).timeGapCount).toBe(0);
    expect(analyzeBarTimes(displayTimes, periodSec).duplicateTimeCount).toBe(0);
  });

  it('maps 07:15 UTC to 09:15 display wall clock on May 25 2026', () => {
    const utc = Math.floor(Date.UTC(2026, 4, 25, 7, 15, 0) / 1000);
    const display = mapUtcBarOpenSecondsForChartDisplay(utc, timezone, timeframe);
    const d = new Date(display * 1000);

    expect(d.getUTCHours()).toBe(9);
    expect(d.getUTCMinutes()).toBe(15);
  });

  it('has no display duplicates or holes across all of May 25 2026 UTC day', () => {
    const dayStart = Math.floor(Date.UTC(2026, 4, 25, 0, 0, 0) / 1000);
    const barsPerDay = (24 * 60) / 5;
    const displayTimes: number[] = [];

    for (let i = 0; i < barsPerDay; i += 1) {
      const utc = dayStart + i * periodSec;

      displayTimes.push(mapUtcBarOpenSecondsForChartDisplay(utc, timezone, timeframe));
    }

    const analysis = analyzeBarTimes(displayTimes, periodSec);

    expect(analysis.timeGapCount).toBe(0);
    expect(analysis.duplicateTimeCount).toBe(0);
  });
});
