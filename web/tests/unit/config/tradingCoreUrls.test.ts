// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { DEMO_ENDPOINT, TRADING_ENDPOINT } from '@/config/api';
import {
  buildTradingEquitySeriesUrl,
  buildTradingModeSelectionUrl,
  buildTradingModesUrl,
  buildTradingOrdersCancelUrl,
  buildTradingOrdersListUrl,
  buildTradingOrdersPlaceUrl,
  buildTradingPerformanceDailyUrl,
  buildTradingPerformanceSummaryUrl,
  buildTradingPortfolioUrl,
  buildTradingResetUrl,
  buildTradingTradesUrl,
} from '@/config/tradingCoreUrls';
import { TRADING_ACTIVITY_FETCH_LIMIT } from '@/utils/constants/trading';

describe('tradingCoreUrls', () => {
  it('builds fixed-path URLs (modes/mode-selection stay at /trading; orders/reset moved to /demo)', () => {
    expect(buildTradingModesUrl()).toBe(`${TRADING_ENDPOINT}/modes`);
    expect(buildTradingModeSelectionUrl()).toBe(`${TRADING_ENDPOINT}/mode-selection`);
    expect(buildTradingOrdersCancelUrl()).toBe(`${DEMO_ENDPOINT}/orders/cancel`);
    expect(buildTradingOrdersPlaceUrl()).toBe(`${DEMO_ENDPOINT}/orders`);
    expect(buildTradingResetUrl()).toBe(`${DEMO_ENDPOINT}/reset`);
  });

  it('builds performance daily URL with UTC range and optional exchange_connection_id', () => {
    expect(
      buildTradingPerformanceDailyUrl({
        startDate: '2026-04-01',
        endDate: '2026-04-30',
        mode: 'demo',
      })
    ).toBe(
      `${TRADING_ENDPOINT}/performance/daily?start_date=2026-04-01&end_date=2026-04-30&mode=demo`
    );

    expect(
      buildTradingPerformanceDailyUrl({
        startDate: '2026-04-01',
        endDate: '2026-04-30',
        mode: 'paper',
        exchangeConnectionId: 'conn-1',
      })
    ).toContain('exchange_connection_id=conn-1');
  });

  it('builds demo portfolio URL with optional exchange_connection_id (no mode on wire)', () => {
    expect(buildTradingPortfolioUrl('demo')).toBe(`${DEMO_ENDPOINT}/portfolio`);
    expect(buildTradingPortfolioUrl('demo', 'c9')).toContain('exchange_connection_id=c9');
    expect(buildTradingPortfolioUrl('demo', 'c9')).toMatch(/^.*\/demo\/portfolio\?/);
  });

  it('builds demo trades URL with limit from TRADING_ACTIVITY_FETCH_LIMIT', () => {
    expect(buildTradingTradesUrl('demo', null, null)).toBe(
      `${DEMO_ENDPOINT}/trades?limit=${TRADING_ACTIVITY_FETCH_LIMIT}`
    );
    expect(buildTradingTradesUrl('demo', 'cx', '2026-04-17')).toContain('trade_date=2026-04-17');
  });

  it('builds demo orders list URL with the same limit constant as trades', () => {
    expect(buildTradingOrdersListUrl('demo', 'c1')).toBe(
      `${DEMO_ENDPOINT}/orders?limit=${TRADING_ACTIVITY_FETCH_LIMIT}&exchange_connection_id=c1`
    );
  });

  it('builds performance summary URL with UTC range and optional exchange_connection_id', () => {
    expect(
      buildTradingPerformanceSummaryUrl({
        startDate: '2026-04-01',
        endDate: '2026-04-30',
        mode: 'demo',
      })
    ).toBe(
      `${TRADING_ENDPOINT}/performance/summary?start_date=2026-04-01&end_date=2026-04-30&mode=demo`
    );

    expect(
      buildTradingPerformanceSummaryUrl({
        startDate: '2026-04-01',
        endDate: '2026-04-30',
        mode: 'paper',
        exchangeConnectionId: 'conn-9',
      })
    ).toContain('exchange_connection_id=conn-9');

    const symUrl = buildTradingPerformanceSummaryUrl({
      startDate: '2026-04-01',
      endDate: '2026-04-30',
      mode: 'paper',
      exchangeConnectionId: 'conn-9',
      symbol: 'BTC/USDT',
    });

    expect(symUrl).toContain('symbol=BTC%2FUSDT');
  });

  it('builds equity-series URL with UTC range, optional connection and optional symbol', () => {
    expect(
      buildTradingEquitySeriesUrl({
        startDate: '2026-04-01',
        endDate: '2026-04-30',
        mode: 'demo',
      })
    ).toBe(
      `${TRADING_ENDPOINT}/performance/equity-series?start_date=2026-04-01&end_date=2026-04-30&mode=demo`
    );

    const paperUrl = buildTradingEquitySeriesUrl({
      startDate: '2026-04-01',
      endDate: '2026-04-30',
      mode: 'paper',
      exchangeConnectionId: 'conn-9',
      symbol: 'BTC/USDT',
    });

    expect(paperUrl).toContain('exchange_connection_id=conn-9');
    expect(paperUrl).toContain('symbol=BTC%2FUSDT');
  });
});
