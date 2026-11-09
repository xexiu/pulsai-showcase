// @vitest-environment node
import { describe, expect, it } from 'vitest';

import type { ExchangeConnection } from '@/types/tradingBarrel';
import { firstActiveExchangeConnection } from '@/utils/trading/first-active-exchange-connection';

function conn(overrides: Partial<ExchangeConnection>): ExchangeConnection {
  return {
    id: 'id',
    exchange: 'binance',
    status: 'active',
    permissions: {},
    has_testnet: true,
    fee_rate_maker: null,
    fee_rate_taker: null,
    last_verified_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('firstActiveExchangeConnection', () => {
  it('returns undefined when list is empty or undefined', () => {
    expect(firstActiveExchangeConnection(undefined)).toBeUndefined();
    expect(firstActiveExchangeConnection([])).toBeUndefined();
  });

  it('returns undefined when no connection is active', () => {
    expect(
      firstActiveExchangeConnection([
        conn({ status: 'disconnected' }),
        conn({ id: '2', status: 'error' }),
      ])
    ).toBeUndefined();
  });

  it('returns the first active connection in list order', () => {
    const a = conn({ id: 'a', exchange: 'binance', status: 'disconnected' });
    const b = conn({ id: 'b', exchange: 'bitget', status: 'active' });

    expect(firstActiveExchangeConnection([a, b])).toEqual(b);
  });

  it('skips disconnected rows before an active one', () => {
    const active = conn({ id: 'x', exchange: 'okx', status: 'active' });

    expect(firstActiveExchangeConnection([conn({ status: 'disconnected' }), active])).toEqual(
      active
    );
  });
});
