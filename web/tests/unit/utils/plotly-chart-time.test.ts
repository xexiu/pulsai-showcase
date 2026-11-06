// @vitest-environment node
/**
 * Plotly x-axis: real UTC epoch ms (not LWC timeToTz / mapUtcBarOpenSecondsForChartDisplay).
 */

import { describe, expect, it } from 'vitest';

import { timestampToPlotlyXMs } from '@/utils/plotly-chart-time';

describe('timestampToPlotlyXMs', () => {
  it('maps bar open to UTC epoch ms (same as Date.parse)', () => {
    const iso = '2026-01-01T00:00:00.000Z';
    const ms = timestampToPlotlyXMs(iso, 'UTC', '1h');

    expect(ms).toBe(Date.parse(iso));
  });

  it('ignores chart timezone (regression: no +2h vs UTC for Europe/Madrid)', () => {
    const iso = '2026-04-11T20:00:00.000Z';
    const utcMs = timestampToPlotlyXMs(iso, 'UTC', '1h');
    const madridMs = timestampToPlotlyXMs(iso, 'Europe/Madrid', '1h');

    expect(utcMs).toBe(madridMs);
    expect(utcMs).toBe(Date.parse(iso));
  });

  it('uses raw UTC seconds for any timeframe (intraday included)', () => {
    const iso = '2026-01-01T00:00:00.000Z';
    const sec = Math.floor(Date.parse(iso) / 1000);
    const ms = timestampToPlotlyXMs(iso, 'Europe/Madrid', '4h');

    expect(ms).toBe(sec * 1000);
  });
});
