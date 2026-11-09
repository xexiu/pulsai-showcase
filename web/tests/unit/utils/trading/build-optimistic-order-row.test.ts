// @vitest-environment node
import { describe, expect, it } from 'vitest';

import type { PlaceOrderRequest } from '@/types/tradingBarrel';
import { PAPER_ORDER_STATUS } from '@/utils/constants/trading';
import {
  buildOptimisticOrderRow,
  isOptimisticOrderRow,
  OPTIMISTIC_ORDER_ID_PREFIX,
} from '@/utils/trading/build-optimistic-order-row';

const BASE: PlaceOrderRequest = {
  mode: 'paper',
  exchange_connection_id: 'conn-1',
  side: 'buy',
  symbol: 'BTC/USDT',
  price: '70000',
  order_execution: 'limit',
  amount_usd: '100',
  amount_btc: null,
};

describe('buildOptimisticOrderRow', () => {
  it('returns a pending OrderRow with an optimistic-prefixed id', () => {
    const row = buildOptimisticOrderRow(BASE);

    expect(row.id.startsWith(OPTIMISTIC_ORDER_ID_PREFIX)).toBe(true);
    expect(row.status).toBe(PAPER_ORDER_STATUS.PENDING);
    expect(row.symbol).toBe('BTC/USDT');
    expect(row.side).toBe('buy');
    expect(row.order_type).toBe('limit');
    expect(row.limit_price).toBe('70000');
    expect(row.amount_usd).toBe('100');
  });

  it('omits limit_price for market orders even if a price is sent', () => {
    const row = buildOptimisticOrderRow({ ...BASE, order_execution: 'market', price: '70000' });

    expect(row.order_type).toBe('market');
    expect(row.limit_price).toBeNull();
  });

  it('propagates SL/TP/marketType/leverage', () => {
    const row = buildOptimisticOrderRow({
      ...BASE,
      stop_loss_price: '65000',
      take_profit_price: '80000',
      market_type: 'swap',
      leverage: 10,
    });

    expect(row.stop_loss_price).toBe('65000');
    expect(row.take_profit_price).toBe('80000');
    expect(row.market_type).toBe('swap');
    expect(row.leverage).toBe(10);
  });

  it('isOptimisticOrderRow distinguishes optimistic from server rows', () => {
    const opt = buildOptimisticOrderRow(BASE);

    expect(isOptimisticOrderRow(opt)).toBe(true);
    expect(isOptimisticOrderRow({ id: 'real-uuid-123' })).toBe(false);
  });

  it('generates unique ids across calls', () => {
    const ids = new Set(Array.from({ length: 20 }, () => buildOptimisticOrderRow(BASE).id));

    expect(ids.size).toBe(20);
  });
});
