// @vitest-environment node
/**
 * Chart fetch limits: per-TF minimum visible history vs API cap.
 *
 * Lower intraday TFs (5m/15m/30m) request ≥2 weeks of bars so the chart has
 * usable multi-session context. Coarser TFs keep the global 2-day floor + candle
 * floors. Payload is still capped at MARKET_OHLCV_API_MAX_CANDLES (must match BE).
 *
 * @see apps/web/src/utils/chart-time/limits.ts
 */

import { describe, expect, it } from 'vitest';

import {
  getChartOhlcvSharedCandleLimit,
  getFullChartCandleFetchLimit,
  getOhlcvDashboardCandleLimit,
  getSignalLimitForTimeframe,
} from '@/utils/chart-time/limits';
import {
  CHART_LOWER_TF_MIN_HISTORY_DAYS,
  MARKET_OHLCV_API_MAX_CANDLES,
  SIGNAL_MAX_WEEK_CAP,
  TIMEFRAME_HISTORY_DAYS_OVERRIDES,
} from '@/utils/constants';

describe('getOhlcvDashboardCandleLimit', () => {
  it('5m requests two weeks of bars (14 * 288), under the API max', () => {
    expect(TIMEFRAME_HISTORY_DAYS_OVERRIDES['5m']).toBe(CHART_LOWER_TF_MIN_HISTORY_DAYS);
    expect(getOhlcvDashboardCandleLimit('5m')).toBe(14 * 288);
    expect(getOhlcvDashboardCandleLimit('5m')).toBeLessThanOrEqual(MARKET_OHLCV_API_MAX_CANDLES);
  });

  it('15m requests two weeks of bars (14 * 96)', () => {
    expect(TIMEFRAME_HISTORY_DAYS_OVERRIDES['15m']).toBe(CHART_LOWER_TF_MIN_HISTORY_DAYS);
    expect(getOhlcvDashboardCandleLimit('15m')).toBe(14 * 96);
  });

  it('30m requests two weeks of bars (14 * 48)', () => {
    expect(TIMEFRAME_HISTORY_DAYS_OVERRIDES['30m']).toBe(CHART_LOWER_TF_MIN_HISTORY_DAYS);
    expect(getOhlcvDashboardCandleLimit('30m')).toBe(14 * 48);
  });

  it('keeps 200 for 1h (floor exceeds 2-day bar count of 48)', () => {
    expect(getOhlcvDashboardCandleLimit('1h')).toBe(200);
  });

  it('1m requests the 2-day default window, capped at the API max', () => {
    const twoDayBars = 2 * 1440;

    expect(getOhlcvDashboardCandleLimit('1m')).toBe(
      Math.min(twoDayBars, MARKET_OHLCV_API_MAX_CANDLES)
    );
  });
});

describe('getFullChartCandleFetchLimit', () => {
  it('15m full chart loads two weeks (not the legacy 500-bar floor)', () => {
    expect(getFullChartCandleFetchLimit('15m')).toBe(14 * 96);
  });

  it('5m full chart loads two weeks under the raised API max', () => {
    expect(getFullChartCandleFetchLimit('5m')).toBe(14 * 288);
  });

  it('keeps 500 floor for 1h on full chart (above the 2-day bar count of 48)', () => {
    expect(getFullChartCandleFetchLimit('1h')).toBe(500);
  });

  it('1m full chart is capped at the API max when 2-day bars exceed it', () => {
    const twoDayBars = 2 * 1440;

    expect(getFullChartCandleFetchLimit('1m')).toBe(
      Math.min(Math.max(500, twoDayBars), MARKET_OHLCV_API_MAX_CANDLES)
    );
  });
});

describe('getChartOhlcvSharedCandleLimit — the SERVED value wins', () => {
  it('uses the limit the backend published for the timeframe', () => {
    // The server owns this number (GET /config/public -> TimeframePublicOption.chart_candle_limit)
    // because the chart-indicators response cache is keyed by `limit`. A client that derives its
    // own and disagrees requests a key nothing warmed: 1308ms at 5m/4032 on prod, vs 397ms warm.
    expect(getChartOhlcvSharedCandleLimit('1h', 777)).toBe(777);
  });

  it('falls back to the local rule when the server did not send one', () => {
    // A cached older API response, or the offline fallback, may not carry the field.
    expect(getChartOhlcvSharedCandleLimit('1h', undefined)).toBe(
      getFullChartCandleFetchLimit('1h')
    );
    expect(getChartOhlcvSharedCandleLimit('1h')).toBe(getFullChartCandleFetchLimit('1h'));
    expect(getChartOhlcvSharedCandleLimit('1h', null)).toBe(getFullChartCandleFetchLimit('1h'));
  });

  it('ignores a non-positive served value rather than requesting zero candles', () => {
    // A 0 would otherwise sail through as "served" and ask the API for an empty chart.
    expect(getChartOhlcvSharedCandleLimit('5m', 0)).toBe(getFullChartCandleFetchLimit('5m'));
    expect(getChartOhlcvSharedCandleLimit('5m', -1)).toBe(getFullChartCandleFetchLimit('5m'));
  });

  it('agrees with the local rule for the timeframes the server actually serves today', () => {
    // Both implementations are live until the local one is deleted, so their agreement is a
    // property worth asserting rather than assuming.
    for (const timeframe of ['5m', '15m', '30m', '1h', '4h', '1d']) {
      expect(
        getChartOhlcvSharedCandleLimit(timeframe, getFullChartCandleFetchLimit(timeframe))
      ).toBe(getChartOhlcvSharedCandleLimit(timeframe));
    }
  });
});

describe('MARKET_OHLCV_API_MAX_CANDLES', () => {
  it('is high enough for two weeks of 5m bars (BE Query le must match)', () => {
    expect(MARKET_OHLCV_API_MAX_CANDLES).toBeGreaterThanOrEqual(14 * 288);
  });
});

describe('getSignalLimitForTimeframe', () => {
  /**
   * THE REPORTED BUG: "charts were showing all DB signals, now shows only the last 5 or so".
   *
   * MEASURED against prod 2026-09-04 (BTC/USDT): 1d holds 87 signal rows over 45 distinct bars
   * and the chart asked for 7, because the window was `perDay * 7` — one WEEK of candles — while
   * the chart draws getChartOhlcvSharedCandleLimit() candles, floor 500.
   */
  it.each(['1d', '12h', '8h', '6h', '4h', '1h', '5m', '15m', '30m'])(
    'covers every candle the chart draws on %s',
    (tf) => {
      expect(getSignalLimitForTimeframe(tf)).toBe(
        Math.min(getChartOhlcvSharedCandleLimit(tf), SIGNAL_MAX_WEEK_CAP)
      );
    }
  );

  it('asks for far more than one week of DAILY bars', () => {
    // The old rule returned exactly 7 here, which is the whole reported defect.
    expect(getSignalLimitForTimeframe('1d')).toBeGreaterThan(7);
  });

  it('never exceeds the ceiling the API enforces on `bars`', () => {
    for (const tf of ['5m', '15m', '30m', '1h', '4h', '1d']) {
      expect(getSignalLimitForTimeframe(tf)).toBeLessThanOrEqual(SIGNAL_MAX_WEEK_CAP);
    }
  });

  it('draws markers over the SERVED window, not a locally derived one', () => {
    // THE FOURTH RECURRENCE, closed here. Once the server began publishing the candle limit,
    // "derive it from the candle-limit SoT" stopped meaning "call the local function": this
    // window derived locally while the chart requested the served value. One config change apart
    // and markers land on a subset of the drawn candles, which IS the reported bug.
    const served = 321;

    expect(served).not.toBe(getFullChartCandleFetchLimit('1h'));
    expect(getSignalLimitForTimeframe('1h', served)).toBe(Math.min(served, SIGNAL_MAX_WEEK_CAP));
  });

  it('asks for exactly the candles the chart requests, under any served value', () => {
    // The invariant in one line: same served input, same number on both sides. This is the
    // property the three previous fixes each restored by hand and none of them pinned.
    for (const served of [321, 1234, 4032]) {
      for (const tf of ['5m', '1h', '4h', '1d']) {
        expect(getSignalLimitForTimeframe(tf, served)).toBe(
          Math.min(getChartOhlcvSharedCandleLimit(tf, served), SIGNAL_MAX_WEEK_CAP)
        );
      }
    }
  });

  it('keeps the 1w special case whatever the server serves for the chart', () => {
    // 1w markers are capped at 2 bars deliberately; a served chart limit must not widen them.
    expect(getSignalLimitForTimeframe('1w', 5000)).toBe(Math.min(2, SIGNAL_MAX_WEEK_CAP));
  });
});
