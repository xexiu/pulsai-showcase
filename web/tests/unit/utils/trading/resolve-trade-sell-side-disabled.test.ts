// @vitest-environment node
/**
 * resolveTradeSellSideDisabled — spot needs base to sell; perps sell opens short.
 */

import { describe, expect, it } from 'vitest';

import { MARKET_TYPE, TRADING_MODE } from '@/utils/constants/trading';
import { resolveTradeSellSideDisabled } from '@/utils/trading/resolve-trade-sell-side-disabled';

const ready = {
  isAuthenticated: true,
  portfolioLoading: false,
  portfolioError: false,
};

describe('resolveTradeSellSideDisabled', () => {
  it('returns false when portfolio is not ready (do not gate sell until balances load)', () => {
    expect(
      resolveTradeSellSideDisabled({
        ...ready,
        portfolio: undefined,
        modeStr: TRADING_MODE.PAPER,
        marketType: MARKET_TYPE.SPOT,
        baseAsset: 'BTC',
      })
    ).toBe(false);
  });

  it('returns false for live mode (sell gating deferred to product rules)', () => {
    expect(
      resolveTradeSellSideDisabled({
        ...ready,
        portfolio: { btc_balance: '0' },
        modeStr: TRADING_MODE.LIVE,
        marketType: MARKET_TYPE.SPOT,
        baseAsset: 'BTC',
      })
    ).toBe(false);
  });

  it('disables sell on spot when paper has no free base', () => {
    expect(
      resolveTradeSellSideDisabled({
        ...ready,
        portfolio: { balance: { USDT: { free: 1000 } } },
        modeStr: TRADING_MODE.PAPER,
        marketType: MARKET_TYPE.SPOT,
        baseAsset: 'BTC',
      })
    ).toBe(true);
  });

  it('does not disable sell on swap when paper has no free base (short entry)', () => {
    expect(
      resolveTradeSellSideDisabled({
        ...ready,
        portfolio: { balance: { USDT: { free: 1000 } } },
        modeStr: TRADING_MODE.PAPER,
        marketType: MARKET_TYPE.SWAP,
        baseAsset: 'BTC',
      })
    ).toBe(false);
  });

  it('does not disable sell on swap for demo (futures tab UX)', () => {
    expect(
      resolveTradeSellSideDisabled({
        ...ready,
        portfolio: { btc_balance: '0' },
        modeStr: TRADING_MODE.DEMO,
        marketType: MARKET_TYPE.SWAP,
        baseAsset: 'BTC',
      })
    ).toBe(false);
  });

  it('disables sell on spot demo when btc_balance is zero', () => {
    expect(
      resolveTradeSellSideDisabled({
        ...ready,
        portfolio: { btc_balance: '0' },
        modeStr: TRADING_MODE.DEMO,
        marketType: MARKET_TYPE.SPOT,
        baseAsset: 'BTC',
      })
    ).toBe(true);
  });
});
