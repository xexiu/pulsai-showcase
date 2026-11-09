// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  readCcxtPositiveFreeBalance,
  readCcxtUnifiedAssetAmount,
} from '@/utils/trading/ccxt-balance-read';

describe('readCcxtPositiveFreeBalance', () => {
  it('returns null for zero balance (presets ignore dust)', () => {
    expect(readCcxtPositiveFreeBalance({ USDT: { free: 0, total: 0 } }, 'USDT')).toBeNull();
  });

  it('returns positive free amount', () => {
    expect(
      readCcxtPositiveFreeBalance({ USDT: { free: 9992.2962, total: 9992.2962 } }, 'USDT')
    ).toBe(9992.2962);
  });
});

describe('readCcxtUnifiedAssetAmount', () => {
  it('returns zero when exchange reports zero USDT', () => {
    expect(readCcxtUnifiedAssetAmount({ USDT: { free: 0, total: 0 } }, 'USDT')).toBe(0);
  });

  it('reads quote and base from unified balance', () => {
    const bal = {
      USDT: { free: 9992.2962, total: 9992.2962 },
      BTC: { free: 0.01, total: 0.01 },
    };

    expect(readCcxtUnifiedAssetAmount(bal, 'USDT')).toBe(9992.2962);
    expect(readCcxtUnifiedAssetAmount(bal, 'BTC')).toBe(0.01);
  });

  it('matches asset codes case-insensitively (CCXT venue variance)', () => {
    const bal = {
      usdt: { free: 100, total: 100 },
    };

    expect(readCcxtUnifiedAssetAmount(bal, 'USDT')).toBe(100);
    expect(readCcxtPositiveFreeBalance(bal, 'USDT')).toBe(100);
  });
});
