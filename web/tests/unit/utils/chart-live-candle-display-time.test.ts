// @vitest-environment node
/**
 * @see apps/web/src/utils/chart-live-candle-display-time.ts
 */

import { describe, expect, it } from 'vitest';

import { resolveLiveCandleDisplayTime } from '@/utils/chart-live-candle-display-time';
import { mapUtcBarOpenSecondsForChartDisplay } from '@/utils/chart-timezone';

describe('resolveLiveCandleDisplayTime', () => {
  const timezone = 'Europe/Madrid';
  const timeframe = '5m';
  const period = 300;

  it('caps live display to anchor+period when live is many periods ahead of stale data', () => {
    const dataLastUtc = 1_779_794_100;
    const dataLastDisplay = mapUtcBarOpenSecondsForChartDisplay(dataLastUtc, timezone, timeframe);
    const chartLastDisplay = dataLastDisplay + period;
    const liveUtc = dataLastUtc + period * 4;

    const result = resolveLiveCandleDisplayTime({
      dataLastUtc,
      liveUtc,
      chartLastDisplayTime: chartLastDisplay,
      timezone,
      timeframe,
    });

    expect(result).not.toBeNull();
    expect(result?.cappedAhead).toBe(true);
    expect(result?.displayTime).toBe(chartLastDisplay + period);
  });

  it('anchors on dataLastDisplay when chart ref is far ahead of historical (post-clear)', () => {
    const dataLastUtc = 1_779_794_100;
    const dataLastDisplay = mapUtcBarOpenSecondsForChartDisplay(dataLastUtc, timezone, timeframe);
    const staleChartRef = dataLastDisplay + period * 8;

    const result = resolveLiveCandleDisplayTime({
      dataLastUtc,
      liveUtc: dataLastUtc,
      chartLastDisplayTime: staleChartRef,
      timezone,
      timeframe,
    });

    expect(result?.anchorDisplay).toBe(dataLastDisplay);
    expect(result?.displayTime).toBe(dataLastDisplay);
  });

  it('keeps liveDisplay when REST is one closed bar behind WS (BB extends separately)', () => {
    const dataLastUtc = 1_779_893_400;
    const liveUtc = dataLastUtc + period * 2;
    const dataLastDisplay = mapUtcBarOpenSecondsForChartDisplay(dataLastUtc, timezone, timeframe);
    const liveDisplay = mapUtcBarOpenSecondsForChartDisplay(liveUtc, timezone, timeframe);

    const result = resolveLiveCandleDisplayTime({
      dataLastUtc,
      liveUtc,
      chartLastDisplayTime: dataLastDisplay,
      timezone,
      timeframe,
    });

    expect(result?.cappedAhead).toBe(false);
    expect(result?.displayTime).toBe(liveDisplay);
    expect(result?.normalizedUtc).toBe(liveUtc);
  });

  it('uses consecutive live display when only one period ahead of anchor', () => {
    const dataLastUtc = 1_779_794_100;
    const chartLastDisplay = mapUtcBarOpenSecondsForChartDisplay(dataLastUtc, timezone, timeframe);
    const liveUtc = dataLastUtc + period;

    const result = resolveLiveCandleDisplayTime({
      dataLastUtc,
      liveUtc,
      chartLastDisplayTime: chartLastDisplay,
      timezone,
      timeframe,
    });

    expect(result?.cappedAhead).toBe(false);
    expect(result?.displayTime).toBe(result?.liveDisplay);
  });
});
