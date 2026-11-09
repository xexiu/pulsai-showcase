// @vitest-environment node
/**
 * Valibot schema for POST /trading/orders bodies — mirrors BE `TradingOrderRequest`
 * validators (`demo_is_spot_only`, `bracket_contract`, `demo_limit_contract`).
 *
 * Slice B7 — catch demo+swap, paper/live spot+SLTP, symbol > 32 chars before a network round trip.
 */

import * as v from 'valibot';
import { describe, expect, it } from 'vitest';

import { placeOrderRequestSchema } from '@/schemas/trading';

const validPaperSwapLimit = {
  mode: 'paper',
  exchange_connection_id: 'conn-1',
  side: 'buy',
  symbol: 'BTC/USDT',
  order_execution: 'limit',
  price: '50000',
  amount_btc: '0.01',
  stop_loss_price: '48000',
  take_profit_price: '55000',
  market_type: 'swap',
  leverage: 5,
} as const;

describe('placeOrderRequestSchema', () => {
  it('accepts a paper swap limit order with SL/TP', () => {
    const out = v.parse(placeOrderRequestSchema, validPaperSwapLimit);

    expect(out.market_type).toBe('swap');
    expect(out.order_execution).toBe('limit');
  });

  it('rejects symbol longer than 32 characters (BE max_length=32)', () => {
    const long = 'X'.repeat(33);
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'demo',
      side: 'buy',
      symbol: `${long}/USDT`,
      price: '50000',
      amount_usd: '100',
    });

    expect(result.success).toBe(false);
  });

  it('rejects demo + market_type=swap (demo is spot-only)', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'demo',
      side: 'buy',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_usd: '100',
      market_type: 'swap',
      leverage: 3,
    });

    expect(result.success).toBe(false);
  });

  it('rejects demo + leverage even on spot', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'demo',
      side: 'buy',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_usd: '100',
      leverage: 3,
    });

    expect(result.success).toBe(false);
  });

  it('accepts paper spot buy + stop_loss_price (defers unsupported venue to API)', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'paper',
      exchange_connection_id: 'conn-1',
      side: 'buy',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_btc: '0.01',
      stop_loss_price: '48000',
    });

    expect(result.success).toBe(true);
  });

  it('accepts live spot buy + take_profit_price (same as paper)', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'live',
      exchange_connection_id: 'conn-live',
      side: 'buy',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_btc: '0.01',
      take_profit_price: '55000',
    });

    expect(result.success).toBe(true);
  });

  it('rejects paper spot sell + stop_loss_price', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'paper',
      exchange_connection_id: 'conn-1',
      side: 'sell',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_btc: '0.01',
      stop_loss_price: '52000',
    });

    expect(result.success).toBe(false);
  });

  it('rejects demo limit with SL or TP (demo_limit_contract V1 deferred)', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'demo',
      side: 'buy',
      symbol: 'BTC/USDT',
      order_execution: 'limit',
      price: '49000',
      amount_usd: '100',
      stop_loss_price: '48000',
    });

    expect(result.success).toBe(false);
  });

  it('accepts paper/live limit swap + SL/TP (happy path for B7)', () => {
    const result = v.safeParse(placeOrderRequestSchema, validPaperSwapLimit);

    expect(result.success).toBe(true);
  });

  it('accepts demo spot buy with bracket (existing behavior)', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'demo',
      side: 'buy',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_usd: '100',
      stop_loss_price: '48000',
      take_profit_price: '55000',
    });

    expect(result.success).toBe(true);
  });

  it('accepts paper swap market with reduce_only true', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'paper',
      exchange_connection_id: 'conn-1',
      side: 'sell',
      symbol: 'BTC/USDT:USDT',
      price: '50000',
      amount_btc: '0.01',
      market_type: 'swap',
      leverage: 3,
      reduce_only: true,
    });

    expect(result.success).toBe(true);
  });

  it('rejects reduce_only true on demo', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'demo',
      side: 'sell',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_usd: '100',
      reduce_only: true,
    });

    expect(result.success).toBe(false);
  });

  it('rejects reduce_only true on spot', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      mode: 'paper',
      exchange_connection_id: 'conn-1',
      side: 'sell',
      symbol: 'BTC/USDT',
      price: '50000',
      amount_btc: '0.01',
      reduce_only: true,
    });

    expect(result.success).toBe(false);
  });

  it('rejects reduce_only true on swap limit', () => {
    const result = v.safeParse(placeOrderRequestSchema, {
      ...validPaperSwapLimit,
      order_execution: 'limit',
      reduce_only: true,
    });

    expect(result.success).toBe(false);
  });
});
