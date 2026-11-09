// @vitest-environment node
/**
 * preset-capital-usd — buying power for trade USD amount presets.
 *
 * Tests cover all mode/side branches plus invalid inputs:
 *   - isDemoPortfolioExhausted: empty / numeric strings / NaN / both-zero / either-positive
 *   - hasSellableBasePosition for demo, paper, and unknown mode
 *   - getPresetCapitalUsd: demo buy fallback string, demo buy with balance, demo sell
 *     (null when no ref price), paper buy via CCXT balance, paper sell via CCXT, unknown mode
 *   - formatUsdAmountFromPercent: invalid capital/percent paths
 */

import { describe, expect, it } from 'vitest';

import {
  formatUsdAmountFromPercent,
  getPresetCapitalUsd,
  hasSellableBasePosition,
  isDemoPortfolioExhausted,
} from '@/utils/trading/preset-capital-usd';

describe('isDemoPortfolioExhausted', () => {
  it('returns true when both balances are missing / zero / NaN', () => {
    expect(isDemoPortfolioExhausted(undefined)).toBe(true);
    expect(isDemoPortfolioExhausted({})).toBe(true);
    expect(isDemoPortfolioExhausted({ balance_usd: '0', btc_balance: '0' })).toBe(true);
    expect(isDemoPortfolioExhausted({ balance_usd: 'nope' })).toBe(true);
  });

  it('returns false when usd is positive', () => {
    expect(isDemoPortfolioExhausted({ balance_usd: '1.0', btc_balance: '0' })).toBe(false);
  });

  it('returns false when btc is positive', () => {
    expect(isDemoPortfolioExhausted({ balance_usd: '0', btc_balance: '0.001' })).toBe(false);
  });
});

describe('hasSellableBasePosition', () => {
  it('demo mode reads btc_balance positively', () => {
    expect(hasSellableBasePosition('demo', { btc_balance: '0.1' }, 'BTC')).toBe(true);
    expect(hasSellableBasePosition('demo', { btc_balance: '0' }, 'BTC')).toBe(false);
    expect(hasSellableBasePosition('demo', undefined, 'BTC')).toBe(false);
  });

  it('paper mode reads CCXT balance[base].free positively', () => {
    const portfolio = {
      balance: { BTC: { free: '0.5', used: '0' } },
    };

    expect(hasSellableBasePosition('paper', portfolio, 'BTC')).toBe(true);
    expect(hasSellableBasePosition('paper', { balance: {} }, 'BTC')).toBe(false);
  });

  it('returns false for unknown mode', () => {
    expect(hasSellableBasePosition('live', { btc_balance: '0.1' }, 'BTC')).toBe(false);
  });
});

describe('getPresetCapitalUsd', () => {
  it('demo buy: returns parsed balance_usd', () => {
    const result = getPresetCapitalUsd({
      modeStr: 'demo',
      side: 'buy',
      portfolio: { balance_usd: '5000' },
      referencePriceUsd: 50000,
      baseAsset: 'BTC',
    });

    expect(result).toBe(5000);
  });

  it('demo buy: falls back to demo default when balance_usd is missing', () => {
    const result = getPresetCapitalUsd({
      modeStr: 'demo',
      side: 'buy',
      portfolio: undefined,
      referencePriceUsd: 50000,
      baseAsset: 'BTC',
    });

    expect(typeof result).toBe('number');
    expect(result).toBeGreaterThan(0);
  });

  it('demo sell: returns btc_balance * referencePriceUsd', () => {
    const result = getPresetCapitalUsd({
      modeStr: 'demo',
      side: 'sell',
      portfolio: { btc_balance: '0.5' },
      referencePriceUsd: 60000,
      baseAsset: 'BTC',
    });

    expect(result).toBe(30000);
  });

  it('demo sell: returns null when no reference price', () => {
    expect(
      getPresetCapitalUsd({
        modeStr: 'demo',
        side: 'sell',
        portfolio: { btc_balance: '0.5' },
        referencePriceUsd: null,
        baseAsset: 'BTC',
      })
    ).toBeNull();
  });

  it('demo sell: returns null when btc_balance is non-positive', () => {
    expect(
      getPresetCapitalUsd({
        modeStr: 'demo',
        side: 'sell',
        portfolio: { btc_balance: '0' },
        referencePriceUsd: 60000,
        baseAsset: 'BTC',
      })
    ).toBeNull();
  });

  it('paper buy: returns quote free balance from CCXT structure (default quote=USDT)', () => {
    const result = getPresetCapitalUsd({
      modeStr: 'paper',
      side: 'buy',
      portfolio: { balance: { USDT: { free: '1234.5', used: '0' } } },
      referencePriceUsd: 1,
      baseAsset: 'BTC',
    });

    expect(result).toBe(1234.5);
  });

  it('paper buy: returns null when no free quote balance', () => {
    expect(
      getPresetCapitalUsd({
        modeStr: 'paper',
        side: 'buy',
        portfolio: { balance: {} },
        referencePriceUsd: 1,
        baseAsset: 'BTC',
      })
    ).toBeNull();
  });

  it('paper sell: returns base free * reference price', () => {
    const result = getPresetCapitalUsd({
      modeStr: 'paper',
      side: 'sell',
      portfolio: { balance: { BTC: { free: '0.25', used: '0' } } },
      referencePriceUsd: 40000,
      baseAsset: 'BTC',
    });

    expect(result).toBe(10000);
  });

  it('paper sell: returns null when no base free balance', () => {
    expect(
      getPresetCapitalUsd({
        modeStr: 'paper',
        side: 'sell',
        portfolio: { balance: {} },
        referencePriceUsd: 40000,
        baseAsset: 'BTC',
      })
    ).toBeNull();
  });

  it('paper sell: returns null when reference price is non-positive', () => {
    expect(
      getPresetCapitalUsd({
        modeStr: 'paper',
        side: 'sell',
        portfolio: { balance: { BTC: { free: '0.25', used: '0' } } },
        referencePriceUsd: 0,
        baseAsset: 'BTC',
      })
    ).toBeNull();
  });

  it('returns null for unknown mode', () => {
    expect(
      getPresetCapitalUsd({
        modeStr: 'live',
        side: 'buy',
        portfolio: { balance: { USDT: { free: '1' } } },
        referencePriceUsd: 1,
        baseAsset: 'BTC',
      })
    ).toBeNull();
  });
});

describe('formatUsdAmountFromPercent', () => {
  it('returns empty string when capitalUsd is non-positive or non-finite', () => {
    expect(formatUsdAmountFromPercent(0, 10)).toBe('');
    expect(formatUsdAmountFromPercent(-1, 10)).toBe('');
    expect(formatUsdAmountFromPercent(Number.NaN, 10)).toBe('');
    expect(formatUsdAmountFromPercent(Number.POSITIVE_INFINITY, 10)).toBe('');
  });

  it('returns empty string when percent is non-positive or non-finite', () => {
    expect(formatUsdAmountFromPercent(100, 0)).toBe('');
    expect(formatUsdAmountFromPercent(100, -10)).toBe('');
    expect(formatUsdAmountFromPercent(100, Number.NaN)).toBe('');
  });

  it('returns 2-decimal-place USD value', () => {
    expect(formatUsdAmountFromPercent(1000, 25)).toBe('250.00');
    expect(formatUsdAmountFromPercent(333.33, 50)).toBe('166.66');
  });
});
