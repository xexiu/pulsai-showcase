// @vitest-environment node
import { describe, expect, it } from 'vitest';

import type { TradingMode } from '@/types/tradingBarrel';
import { TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED } from '@/utils/constants/trading';

describe('TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED', () => {
  it('matches GET /trading/modes wire string (paired with BE TRADING_MODES_JSON_KEY_FUTURES_SUPPORTED)', () => {
    expect(TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED).toBe('futures_paper_supported');
  });

  it('is assignable to keyof TradingMode for bracket reads', () => {
    const _keyProbe: keyof TradingMode = TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED;

    expect(_keyProbe).toBe('futures_paper_supported');
  });
});
