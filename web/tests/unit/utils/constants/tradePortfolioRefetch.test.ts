// @vitest-environment node
/**
 * Portfolio polling for paper/live: backstop when WebSocket lifecycle events are missed
 * (e.g. user acts on the exchange site).
 */
import { describe, expect, it } from 'vitest';

import {
  TRADING_QUERY_STALE_PORTFOLIO_MS,
  TRADING_MODE,
  tradePortfolioRefetchIntervalMs,
} from '@/utils/constants/trading';

describe('tradePortfolioRefetchIntervalMs', () => {
  it('uses the same interval as portfolio stale time for paper and live', () => {
    expect(tradePortfolioRefetchIntervalMs(TRADING_MODE.PAPER)).toBe(
      TRADING_QUERY_STALE_PORTFOLIO_MS
    );
    expect(tradePortfolioRefetchIntervalMs(TRADING_MODE.LIVE)).toBe(
      TRADING_QUERY_STALE_PORTFOLIO_MS
    );
  });

  it('disables interval polling for demo (synthetic portfolio, not CCXT-venue bound)', () => {
    expect(tradePortfolioRefetchIntervalMs(TRADING_MODE.DEMO)).toBe(false);
  });
});
