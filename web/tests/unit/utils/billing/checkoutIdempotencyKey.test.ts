import { afterEach, describe, expect, it } from 'vitest';

import type { BillingCurrency, CheckoutTier } from '@/types/billing-api';
import {
  clearAllBillingCheckoutIdempotencyKeys,
  clearBillingCheckoutIdempotencyKey,
  resolveBillingCheckoutIdempotencyKey,
} from '@/utils/billing/checkoutIdempotencyKey';

const TIER: CheckoutTier = 'pro';
const CURRENCY: BillingCurrency = 'eur';

describe('checkoutIdempotencyKey', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('returns the same key on repeat calls for the same tier and currency', () => {
    const first = resolveBillingCheckoutIdempotencyKey(TIER, CURRENCY);
    const second = resolveBillingCheckoutIdempotencyKey(TIER, CURRENCY);

    expect(second).toBe(first);
    expect(first.length).toBeGreaterThan(0);
  });

  it('uses different keys for different checkout intents', () => {
    const pro = resolveBillingCheckoutIdempotencyKey('pro', 'eur');
    const starter = resolveBillingCheckoutIdempotencyKey('starter', 'eur');

    expect(starter).not.toBe(pro);
  });

  it('clear removes stored key so the next resolve is fresh', () => {
    const first = resolveBillingCheckoutIdempotencyKey(TIER, CURRENCY);

    clearBillingCheckoutIdempotencyKey(TIER, CURRENCY);

    const second = resolveBillingCheckoutIdempotencyKey(TIER, CURRENCY);

    expect(second).not.toBe(first);
  });

  it('clearAll removes every stored checkout idempotency key', () => {
    const proBefore = resolveBillingCheckoutIdempotencyKey('pro', 'eur');
    const starterBefore = resolveBillingCheckoutIdempotencyKey('starter', 'usd');

    clearAllBillingCheckoutIdempotencyKeys();

    const proAfter = resolveBillingCheckoutIdempotencyKey('pro', 'eur');
    const starterAfter = resolveBillingCheckoutIdempotencyKey('starter', 'usd');

    expect(proAfter).not.toBe(proBefore);
    expect(starterAfter).not.toBe(starterBefore);
  });
});
