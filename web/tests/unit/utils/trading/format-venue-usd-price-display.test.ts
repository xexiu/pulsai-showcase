// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { TRADING_BALANCE_UNAVAILABLE_MARK } from '@/utils/constants/trading';
import { formatVenueUsdPriceDisplay } from '@/utils/trading/format-venue-usd-price-display';

describe('formatVenueUsdPriceDisplay', () => {
  it('returns em dash for empty input', () => {
    expect(formatVenueUsdPriceDisplay(null)).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
    expect(formatVenueUsdPriceDisplay(undefined)).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
    expect(formatVenueUsdPriceDisplay('')).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
  });

  it('locale-formats a finite decimal string', () => {
    const out = formatVenueUsdPriceDisplay('82308.64');

    expect(Number.parseFloat(out.replace(/,/g, ''))).toBeCloseTo(82308.64, 4);
  });
});
