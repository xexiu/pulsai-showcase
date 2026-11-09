// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { isTradingOrderCancellable } from '@/utils/trading/is-trading-order-cancellable';

describe('isTradingOrderCancellable', () => {
  it('returns true for pending and open', () => {
    expect(
      isTradingOrderCancellable({
        id: '1',
        symbol: 'BTC/USDT',
        side: 'buy',
        order_type: 'limit',
        status: 'pending',
        amount_usd: '1',
        amount_btc: null,
        limit_price: '1',
        created_at: '',
        updated_at: '',
      })
    ).toBe(true);

    expect(
      isTradingOrderCancellable({
        id: '1',
        symbol: 'BTC/USDT',
        side: 'buy',
        order_type: 'limit',
        status: 'OPEN',
        amount_usd: '1',
        amount_btc: null,
        limit_price: '1',
        created_at: '',
        updated_at: '',
      })
    ).toBe(true);
  });

  it('returns false for filled', () => {
    expect(
      isTradingOrderCancellable({
        id: '1',
        symbol: 'BTC/USDT',
        side: 'buy',
        order_type: 'market',
        status: 'filled',
        amount_usd: '1',
        amount_btc: null,
        limit_price: null,
        created_at: '',
        updated_at: '',
      })
    ).toBe(false);
  });

  it('returns true for partially_filled (paper/live)', () => {
    expect(
      isTradingOrderCancellable({
        id: '1',
        symbol: 'BTC/USDT',
        side: 'buy',
        order_type: 'limit',
        status: 'partially_filled',
        amount_usd: '1',
        amount_btc: '0.01',
        limit_price: '1',
        created_at: '',
        updated_at: '',
      })
    ).toBe(true);
  });

  it('returns false for optimistic (yet-to-confirm) rows even if status is pending', () => {
    expect(
      isTradingOrderCancellable({
        id: 'optimistic-abc-def',
        symbol: 'BTC/USDT',
        side: 'buy',
        order_type: 'limit',
        status: 'pending',
        amount_usd: '1',
        amount_btc: null,
        limit_price: '1',
        created_at: '',
        updated_at: '',
      })
    ).toBe(false);
  });
});
