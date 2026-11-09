// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { MARKET_TYPE } from '@/utils/constants/trading';
import {
  isCcxtUnifiedSwapStyleSymbol,
  isEffectiveSwapMarket,
  resolveEffectiveMarketTypeForActivitySide,
  resolveEffectiveMarketTypeForOrderDisplay,
} from '@/utils/trading/resolve-effective-market-type-for-activity';

describe('resolveEffectiveMarketTypeForActivitySide', () => {
  it('treats BTC/USDT:USDT as swap when API says spot', () => {
    expect(resolveEffectiveMarketTypeForActivitySide('BTC/USDT:USDT', MARKET_TYPE.SPOT)).toBe(
      MARKET_TYPE.SWAP
    );
  });

  it('preserves spot for plain BTC/USDT', () => {
    expect(resolveEffectiveMarketTypeForActivitySide('BTC/USDT', MARKET_TYPE.SPOT)).toBe(
      MARKET_TYPE.SPOT
    );
  });

  it('preserves explicit swap', () => {
    expect(resolveEffectiveMarketTypeForActivitySide('BTC/USDT:USDT', MARKET_TYPE.SWAP)).toBe(
      MARKET_TYPE.SWAP
    );
  });

  it('infers swap when market_type missing but symbol has settle suffix', () => {
    expect(resolveEffectiveMarketTypeForActivitySide('ETH/USDT:USDT', undefined)).toBe(
      MARKET_TYPE.SWAP
    );
  });
});

describe('isCcxtUnifiedSwapStyleSymbol', () => {
  it('detects colon suffix', () => {
    expect(isCcxtUnifiedSwapStyleSymbol('  BTC/USDT:USDT  ')).toBe(true);
    expect(isCcxtUnifiedSwapStyleSymbol('BTC/USDT')).toBe(false);
  });
});

describe('resolveEffectiveMarketTypeForOrderDisplay', () => {
  it('trusts persisted swap when symbol omits CCXT settle suffix (Bitget-style rows)', () => {
    expect(resolveEffectiveMarketTypeForOrderDisplay('BTC/USDT', MARKET_TYPE.SWAP)).toBe(
      MARKET_TYPE.SWAP
    );
  });

  it('still upgrades unified perp symbols when API says spot', () => {
    expect(resolveEffectiveMarketTypeForOrderDisplay('BTC/USDT:USDT', MARKET_TYPE.SPOT)).toBe(
      MARKET_TYPE.SWAP
    );
  });
});

describe('isEffectiveSwapMarket', () => {
  it('is true when market_type is swap even if symbol lacks settle suffix', () => {
    expect(isEffectiveSwapMarket('BTC/USDT', MARKET_TYPE.SWAP)).toBe(true);
  });

  it('is true for unified perp ids', () => {
    expect(isEffectiveSwapMarket('BTC/USDT:USDT', MARKET_TYPE.SWAP)).toBe(true);
  });
});
