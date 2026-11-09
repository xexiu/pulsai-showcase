// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { MARKET_TYPE, TRADING_MODE } from '@/utils/constants/trading';
import {
  buildMarketSellPlaceOrderFromBtcAmount,
  buildPanicCloseSellPlaceOrderInput,
} from '@/utils/trading/build-panic-close-sell-input';

describe('buildPanicCloseSellPlaceOrderInput', () => {
  it('builds market sell with USD notional from full BTC at reference', () => {
    const input = buildPanicCloseSellPlaceOrderInput({
      btcBalanceStr: '0.01',
      referencePriceUsd: 50_000,
      orderSymbol: 'BTC/USDT',
      modeStr: TRADING_MODE.DEMO,
      connectionId: null,
    });

    expect(input.side).toBe('sell');
    expect(input.orderType).toBe('market');
    expect(input.amountUsd).toBe('500.00');
  });

  it('throws when no reference price', () => {
    expect(() =>
      buildPanicCloseSellPlaceOrderInput({
        btcBalanceStr: '0.01',
        referencePriceUsd: null,
        orderSymbol: 'BTC/USDT',
        modeStr: TRADING_MODE.DEMO,
        connectionId: null,
      })
    ).toThrow(/Reference price unavailable/);
  });

  it('includes swap + leverage for perp close so API does not default to spot', () => {
    const input = buildMarketSellPlaceOrderFromBtcAmount({
      btcAmountStr: '0.0013',
      referencePriceUsd: 76_000,
      orderSymbol: 'BTC/USDT:USDT',
      modeStr: TRADING_MODE.PAPER,
      connectionId: 'c1',
      marketType: MARKET_TYPE.SWAP,
      leverage: 3,
    });

    expect(input.marketType).toBe(MARKET_TYPE.SWAP);
    expect(input.leverage).toBe(3);
    expect(input.side).toBe('sell');
    expect(input.reduceOnly).toBe(true);
  });

  it('does not set reduceOnly for swap close in demo (swap not applicable to demo API)', () => {
    const input = buildMarketSellPlaceOrderFromBtcAmount({
      btcAmountStr: '0.001',
      referencePriceUsd: 50_000,
      orderSymbol: 'BTC/USDT:USDT',
      modeStr: TRADING_MODE.DEMO,
      connectionId: null,
      marketType: MARKET_TYPE.SWAP,
      leverage: 2,
    });

    expect(input.reduceOnly).toBeUndefined();
  });
});
