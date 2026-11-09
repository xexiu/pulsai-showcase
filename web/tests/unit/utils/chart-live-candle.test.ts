// @vitest-environment node
/**
 * Unit tests for chart-live-candle (applyLiveCandleUpdate, gap normalization).
 */

import { describe, expect, it, vi } from 'vitest';

import {
  applyLiveCandleUpdate,
  getFormingCandleTime,
  isLiveCandleAlignedWithChartHistory,
} from '@/utils/chart-live-candle';
import { mapUtcBarOpenSecondsForChartDisplay } from '@/utils/chart-timezone';

describe('chart-live-candle', () => {
  describe('getFormingCandleTime', () => {
    it('returns numeric time from live candle', () => {
      const t = 1704067200;

      expect(getFormingCandleTime({ time: t, open: 1, high: 2, low: 0, close: 1.5 })).toBe(t);
    });

    it('returns null when live candle is null or undefined', () => {
      expect(getFormingCandleTime(null)).toBeNull();
      expect(getFormingCandleTime(undefined)).toBeNull();
    });
  });

  describe('isLiveCandleAlignedWithChartHistory', () => {
    it('rejects 5m kline open merged into 15m history', () => {
      const lastHistoricalUtc = 1_779_857_100;
      const liveUtc = 1_779_858_300;

      expect(isLiveCandleAlignedWithChartHistory(liveUtc, lastHistoricalUtc, '15m')).toBe(false);
    });

    it('accepts forming bar one period after last closed bar', () => {
      const period5m = 300;
      const lastHistoricalUtc = 1_779_858_000;
      const liveUtc = lastHistoricalUtc + period5m;

      expect(isLiveCandleAlignedWithChartHistory(liveUtc, lastHistoricalUtc, '5m')).toBe(true);
    });

    it('accepts 1w forming bar on Monday after last closed Monday week (BE weekly anchor)', () => {
      const period1w = 7 * 24 * 60 * 60;
      const lastHistoricalUtc = Math.floor(Date.UTC(2026, 4, 25) / 1000);
      const liveUtc = Math.floor(Date.UTC(2026, 5, 1) / 1000);

      expect(liveUtc % period1w).not.toBe(0);
      expect(isLiveCandleAlignedWithChartHistory(liveUtc, lastHistoricalUtc, '1w')).toBe(true);
    });

    it('accepts 3d forming bar on Binance epoch+1d grid after last closed 3d', () => {
      const period3d = 3 * 24 * 60 * 60;
      const lastHistoricalUtc = Math.floor(Date.UTC(2026, 7, 6) / 1000); // Aug 6
      const liveUtc = Math.floor(Date.UTC(2026, 7, 9) / 1000); // Aug 9 Binance open

      expect(liveUtc % period3d).not.toBe(0);
      expect(isLiveCandleAlignedWithChartHistory(liveUtc, lastHistoricalUtc, '3d')).toBe(true);
    });
  });

  describe('applyLiveCandleUpdate', () => {
    it('paints new forming bar when first tick is flat at previous close (post-close freeze regression)', () => {
      const updateMock = vi.fn();
      const ref = { current: { update: updateMock } };
      const period5m = 300;
      const lastHistoricalUtc = 1_779_858_000;
      const liveUtc = lastHistoricalUtc + period5m;
      const prevClose = 75_803.41;
      const data = [
        {
          time: lastHistoricalUtc - period5m,
          open: 75_800,
          high: 75_810,
          low: 75_795,
          close: 75_801,
        },
        {
          time: lastHistoricalUtc,
          open: 75_801,
          high: 75_805,
          low: 75_798,
          close: prevClose,
        },
      ];
      const liveCandle = {
        time: liveUtc,
        open: prevClose,
        high: prevClose,
        low: prevClose,
        close: prevClose,
      };

      applyLiveCandleUpdate(ref as never, data, liveCandle, '5m');

      expect(updateMock).toHaveBeenCalledTimes(1);
      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          time: liveUtc,
          open: prevClose,
          close: prevClose,
        })
      );
    });

    it('writes live OHLC at the LIVE bar slot when REST is multiple periods behind WS (Bug B fix, 2026-05-30)', () => {
      // SoT pin (Bug B, full-chart 1px / corrupted just-closed bar):
      //
      // Pre-fix: if live was at 8:00 and historical ended at 6:00, the live
      // merge "snapped back" to 7:00 — painting T8's forming OHLC onto the
      // missing T7 slot. On the full chart, where chart-indicators cache
      // doesn't rotate quickly enough at bar close to trigger a corrective
      // setData, T7's bar stayed corrupted as a thin/degenerate candle that
      // pretended to be T7's price action.
      //
      // Post-fix: write at the live bar's actual slot (T8). LWC renders a
      // visible gap from T6 to T8 until REST catches up — far less misleading
      // than fabricating OHLC at T7. The REST refetches on
      // ``useFullChartIndicatorsRefetchOnLivePeriod`` /
      // ``useSignalHistoryRefetchOnClosedCandle`` are the SoT for filling the
      // gap.
      const updateMock = vi.fn();
      const ref = { current: { update: updateMock } };
      const period1h = 3600;
      const t6 = 6 * period1h;
      const t7 = 7 * period1h;
      const t8 = 8 * period1h;
      const data = [
        { time: t6 - period1h, open: 1, high: 2, low: 0, close: 1.5 },
        { time: t6, open: 1.5, high: 2, low: 1, close: 1.8 },
      ];
      const liveCandle = {
        time: t8,
        open: 1.8,
        high: 2.1,
        low: 1.7,
        close: 2,
      };

      applyLiveCandleUpdate(ref as never, data, liveCandle, '1h');

      expect(updateMock).toHaveBeenCalledTimes(1);
      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          time: t8, // NOT t7 — corrupting the missing slot was the bug
          open: liveCandle.open,
          high: liveCandle.high,
          low: liveCandle.low,
          close: liveCandle.close,
        })
      );
      // Explicit: T7's slot must never receive a fabricated OHLC write.
      expect(updateMock).not.toHaveBeenCalledWith(expect.objectContaining({ time: t7 }));
    });

    it('dedupes identical consecutive updates (React strict-mode double effect)', () => {
      const updateMock = vi.fn();
      const ref = { current: { update: updateMock } };
      const data = [{ time: 1_700_000_000, open: 1, high: 2, low: 0.5, close: 1.5 }];
      const liveCandle = { time: 1_700_000_300, open: 1.5, high: 2, low: 1, close: 1.8 };

      applyLiveCandleUpdate(ref as never, data, liveCandle, '5m');
      applyLiveCandleUpdate(ref as never, data, liveCandle, '5m');

      expect(updateMock).toHaveBeenCalledTimes(1);
    });

    it('maps intraday live bar with timeToTz when timezone is set', () => {
      const updateMock = vi.fn();
      const ref = { current: { update: updateMock } };
      const timezone = 'Europe/Madrid';
      const timeframe = '5m';
      const dataLastUtc = 1_779_794_100;
      const liveUtc = dataLastUtc + 300;
      const data = [{ time: dataLastUtc, open: 1, high: 2, low: 0.5, close: 1.5 }];
      const liveCandle = {
        time: liveUtc,
        open: 1.5,
        high: 2,
        low: 1,
        close: 1.8,
      };
      const expectedDisplay = mapUtcBarOpenSecondsForChartDisplay(liveUtc, timezone, timeframe);

      applyLiveCandleUpdate(ref as never, data, liveCandle, timeframe, timezone);

      expect(updateMock).toHaveBeenCalledWith(expect.objectContaining({ time: expectedDisplay }));
    });
  });
});
