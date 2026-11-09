// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { MARKET_TYPE } from '@/utils/constants/trading';
import { resolvePaperOpenOrderMarkPriceDisplay } from '@/utils/trading/resolve-open-order-mark-price-display';

function parseLocaleNumber(s: string): number {
  return Number.parseFloat(s.replace(/,/g, ''));
}

describe('resolvePaperOpenOrderMarkPriceDisplay', () => {
  it('prefers venue mark for swap when present', () => {
    const out = resolvePaperOpenOrderMarkPriceDisplay({
      marketType: MARKET_TYPE.SWAP,
      venueMarkPrice: '76100.5',
      pageMarkUsd: 99999,
    });

    expect(parseLocaleNumber(out)).toBeCloseTo(76100.5, 4);
  });

  it('falls back to page mark when swap venue mark missing', () => {
    const out = resolvePaperOpenOrderMarkPriceDisplay({
      marketType: MARKET_TYPE.SWAP,
      venueMarkPrice: null,
      pageMarkUsd: 82000.25,
    });

    expect(parseLocaleNumber(out)).toBeCloseTo(82000.25, 4);
  });

  it('uses page mark for spot even if venue mark present', () => {
    const out = resolvePaperOpenOrderMarkPriceDisplay({
      marketType: MARKET_TYPE.SPOT,
      venueMarkPrice: '76100',
      pageMarkUsd: 50000,
    });

    expect(parseLocaleNumber(out)).toBeCloseTo(50000, 4);
  });
});
