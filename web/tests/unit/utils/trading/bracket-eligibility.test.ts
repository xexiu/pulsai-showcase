// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { MARKET_TYPE, ORDER_SIDE, TRADING_MODE } from '@/utils/constants/trading';
import {
  isSpotPlanBracketVenueSupported,
  shouldAttachBracketPrices,
  shouldSendSpotBracketPrices,
} from '@/utils/trading/bracket-eligibility';

describe('bracket-eligibility', () => {
  it.each([
    [TRADING_MODE.DEMO, ORDER_SIDE.BUY, MARKET_TYPE.SPOT, true],
    [TRADING_MODE.PAPER, ORDER_SIDE.BUY, MARKET_TYPE.SPOT, true],
    [TRADING_MODE.PAPER, ORDER_SIDE.SELL, MARKET_TYPE.SWAP, true],
    [TRADING_MODE.PAPER, ORDER_SIDE.SELL, MARKET_TYPE.SPOT, false],
    [TRADING_MODE.LIVE, ORDER_SIDE.BUY, undefined, true],
  ])('shouldAttachBracketPrices(%s,%s,%s)=%s', (mode, side, mt, expected) => {
    expect(shouldAttachBracketPrices(mode, side, mt)).toBe(expected);
  });

  it('isSpotPlanBracketVenueSupported is true for bitget only', () => {
    expect(isSpotPlanBracketVenueSupported('bitget')).toBe(true);
    expect(isSpotPlanBracketVenueSupported('BITGET')).toBe(true);
    expect(isSpotPlanBracketVenueSupported('kraken')).toBe(false);
    expect(isSpotPlanBracketVenueSupported(null)).toBe(false);
  });

  it('shouldSendSpotBracketPrices omits unsupported spot venue when id provided', () => {
    expect(
      shouldSendSpotBracketPrices(TRADING_MODE.PAPER, ORDER_SIDE.BUY, MARKET_TYPE.SPOT, 'kraken')
    ).toBe(false);
    expect(
      shouldSendSpotBracketPrices(TRADING_MODE.PAPER, ORDER_SIDE.BUY, MARKET_TYPE.SPOT, 'bitget')
    ).toBe(true);
    expect(
      shouldSendSpotBracketPrices(TRADING_MODE.PAPER, ORDER_SIDE.BUY, MARKET_TYPE.SPOT, undefined)
    ).toBe(true);
  });
});
