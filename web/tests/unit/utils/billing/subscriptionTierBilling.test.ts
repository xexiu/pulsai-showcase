// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  isFreeSubscriptionTier,
  resolvePricingCardPaidAction,
} from '@/utils/billing/subscriptionTierBilling';
import { SUBSCRIPTION_TIERS } from '@/utils/constants';

describe('isFreeSubscriptionTier', () => {
  it('treats missing tier as free', () => {
    expect(isFreeSubscriptionTier(undefined)).toBe(true);
    expect(isFreeSubscriptionTier(null)).toBe(true);
  });

  it('returns true only for free', () => {
    expect(isFreeSubscriptionTier(SUBSCRIPTION_TIERS.FREE)).toBe(true);
    expect(isFreeSubscriptionTier(SUBSCRIPTION_TIERS.STARTER)).toBe(false);
    expect(isFreeSubscriptionTier(SUBSCRIPTION_TIERS.PRO)).toBe(false);
    expect(isFreeSubscriptionTier(SUBSCRIPTION_TIERS.ELITE)).toBe(false);
  });
});

describe('resolvePricingCardPaidAction', () => {
  it('returns null when card has no checkout tier (guest-style link cards)', () => {
    expect(resolvePricingCardPaidAction(SUBSCRIPTION_TIERS.FREE, undefined)).toBeNull();
    expect(resolvePricingCardPaidAction(SUBSCRIPTION_TIERS.PRO, undefined)).toBeNull();
  });

  it('returns checkout for free users on paid plan cards', () => {
    expect(resolvePricingCardPaidAction(SUBSCRIPTION_TIERS.FREE, 'starter')).toBe('checkout');
    expect(resolvePricingCardPaidAction(undefined, 'elite')).toBe('checkout');
  });

  it('returns portal for paid users on paid plan cards', () => {
    expect(resolvePricingCardPaidAction(SUBSCRIPTION_TIERS.STARTER, 'pro')).toBe('portal');
    expect(resolvePricingCardPaidAction(SUBSCRIPTION_TIERS.ELITE, 'starter')).toBe('portal');
  });
});
