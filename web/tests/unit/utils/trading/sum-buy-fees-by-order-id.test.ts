// @vitest-environment node
import { describe, expect, it } from 'vitest';

import type { TradeRow } from '@/types/tradingBarrel';
import { sumBuyFeesQuoteByOrderId } from '@/utils/trading/sum-buy-fees-by-order-id';

const base = (
  o: Partial<TradeRow> & Pick<TradeRow, 'id' | 'side' | 'fee' | 'created_at'>
): TradeRow => ({
  order_id: 'o1',
  symbol: 'BTC/USDT',
  btc_amount: '0.1',
  usd_amount: '100',
  price: '1000',
  ...o,
});

describe('sumBuyFeesQuoteByOrderId', () => {
  it('sums fees per order_id across buy and sell ledger rows (swap perp)', () => {
    const trades: TradeRow[] = [
      base({ id: 'a', side: 'sell', fee: '0.05', created_at: '2024-01-01T00:00:00.000Z' }),
      base({
        id: 'b',
        side: 'sell',
        fee: '0.02',
        created_at: '2024-01-02T00:00:00.000Z',
        order_id: 'o1',
      }),
    ];

    const m = sumBuyFeesQuoteByOrderId(trades);

    expect(m.get('o1')).toBeDefined();
    expect(Number.parseFloat(m.get('o1') ?? '0')).toBeCloseTo(0.07, 8);
  });

  it('still sums multiple buy fills on the same order', () => {
    const trades: TradeRow[] = [
      base({ id: 'a', side: 'buy', fee: '0.05', created_at: '2024-01-01T00:00:00.000Z' }),
      base({
        id: 'b',
        side: 'buy',
        fee: '0.02',
        created_at: '2024-01-02T00:00:00.000Z',
        order_id: 'o1',
      }),
    ];

    const m = sumBuyFeesQuoteByOrderId(trades);

    expect(Number.parseFloat(m.get('o1') ?? '0')).toBeCloseTo(0.07, 8);
  });
});
