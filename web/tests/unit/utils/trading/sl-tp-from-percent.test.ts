// @vitest-environment node
/**
 * sl-tp-from-percent — SL / TP price derivation for trade UI.
 *
 * Covers all invalid-input early-returns (NaN/non-finite/non-positive) and the
 * buy/sell sign of the percent factor for both stopLossPriceFromPercent and
 * takeProfitPriceFromPercent, plus formatOrderPriceUsd's filter on tiny/invalid
 * inputs and trailing-zero trim.
 */

import { describe, expect, it } from 'vitest';

import {
  formatOrderPriceUsd,
  stopLossPriceFromPercent,
  takeProfitPriceFromPercent,
} from '@/utils/trading/sl-tp-from-percent';

describe('formatOrderPriceUsd', () => {
  it('returns empty string for NaN / infinity / tiny values', () => {
    expect(formatOrderPriceUsd(Number.NaN)).toBe('');
    expect(formatOrderPriceUsd(Number.POSITIVE_INFINITY)).toBe('');
    expect(formatOrderPriceUsd(0)).toBe('');
    expect(formatOrderPriceUsd(-1)).toBe('');
  });

  it('trims trailing zeros after fixed precision', () => {
    expect(formatOrderPriceUsd(1)).toBe('1');
    expect(formatOrderPriceUsd(1.5)).toBe('1.5');
    expect(formatOrderPriceUsd(1.25)).toBe('1.25');
  });
});

describe('stopLossPriceFromPercent', () => {
  it.each<[number, number]>([
    [Number.NaN, 5],
    [Number.POSITIVE_INFINITY, 5],
    [0, 5],
    [-1, 5],
  ])('returns NaN for invalid entry %p', (entry, percent) => {
    expect(Number.isNaN(stopLossPriceFromPercent('buy', entry, percent))).toBe(true);
  });

  it.each<[number]>([[Number.NaN], [Number.POSITIVE_INFINITY], [0], [-1]])(
    'returns NaN for invalid/non-positive percent %p',
    (percent) => {
      expect(Number.isNaN(stopLossPriceFromPercent('buy', 100, percent))).toBe(true);
    }
  );

  it('buy side: SL is BELOW entry by the percent factor', () => {
    expect(stopLossPriceFromPercent('buy', 100, 10)).toBeCloseTo(90, 6);
  });

  it('sell side: SL is ABOVE entry by the percent factor', () => {
    expect(stopLossPriceFromPercent('sell', 100, 10)).toBeCloseTo(110, 6);
  });
});

describe('takeProfitPriceFromPercent', () => {
  it.each<[number, number]>([
    [Number.NaN, 5],
    [Number.POSITIVE_INFINITY, 5],
    [0, 5],
    [-1, 5],
  ])('returns NaN for invalid entry %p', (entry, percent) => {
    expect(Number.isNaN(takeProfitPriceFromPercent('buy', entry, percent))).toBe(true);
  });

  it.each<[number]>([[Number.NaN], [Number.POSITIVE_INFINITY], [0], [-1]])(
    'returns NaN for invalid/non-positive percent %p',
    (percent) => {
      expect(Number.isNaN(takeProfitPriceFromPercent('buy', 100, percent))).toBe(true);
    }
  );

  it('buy side: TP is ABOVE entry by the percent factor', () => {
    expect(takeProfitPriceFromPercent('buy', 100, 25)).toBeCloseTo(125, 6);
  });

  it('sell side: TP is BELOW entry by the percent factor', () => {
    expect(takeProfitPriceFromPercent('sell', 100, 25)).toBeCloseTo(75, 6);
  });
});
