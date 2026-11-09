// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { hasSellableBasePosition } from '@/utils/trading/preset-capital-usd';

describe('hasSellableBasePosition', () => {
  it('demo: false when btc_balance is zero', () => {
    expect(hasSellableBasePosition('demo', { btc_balance: '0' }, 'BTC')).toBe(false);
  });

  it('demo: true when btc_balance is positive', () => {
    expect(hasSellableBasePosition('demo', { btc_balance: '0.01' }, 'BTC')).toBe(true);
  });

  it('paper: false when CCXT balance has no free base', () => {
    expect(hasSellableBasePosition('paper', { balance: { USDT: { free: 100 } } }, 'BTC')).toBe(
      false
    );
  });

  it('paper: true when CCXT balance has free base', () => {
    expect(hasSellableBasePosition('paper', { balance: { BTC: { free: 0.001 } } }, 'BTC')).toBe(
      true
    );
  });

  it('unknown mode: false', () => {
    expect(hasSellableBasePosition('live', { btc_balance: '1' }, 'BTC')).toBe(false);
  });
});
