// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { TRADING_MODE } from '@/utils/constants/trading';
import { connectionIdForTradingApi } from '@/utils/trading/connection-id-for-trading-api';

describe('connectionIdForTradingApi', () => {
  it('returns null for demo regardless of connection', () => {
    expect(connectionIdForTradingApi(TRADING_MODE.DEMO, 'conn-1')).toBeNull();
    expect(connectionIdForTradingApi(TRADING_MODE.DEMO, null)).toBeNull();
  });

  it('returns connection for paper/live when provided', () => {
    expect(connectionIdForTradingApi(TRADING_MODE.PAPER, 'c1')).toBe('c1');
    expect(connectionIdForTradingApi(TRADING_MODE.LIVE, 'c2')).toBe('c2');
  });

  it('returns null for paper/live when connection missing', () => {
    expect(connectionIdForTradingApi(TRADING_MODE.PAPER, null)).toBeNull();
    expect(connectionIdForTradingApi(TRADING_MODE.LIVE, undefined)).toBeNull();
  });
});
