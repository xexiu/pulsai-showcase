import type { CheckoutTier } from '@/config/queryFetchersBilling';
import { SUBSCRIPTION_TIERS } from '@/utils/constants';

export type PricingCardPaidAction = 'checkout' | 'portal';

/**
 * Whether the account is on the free tier (default when tier is unknown).
 */
export function isFreeSubscriptionTier(tier: string | undefined | null): boolean {
  return (tier ?? SUBSCRIPTION_TIERS.FREE) === SUBSCRIPTION_TIERS.FREE;
}

/**
 * Authenticated pricing-card CTA: Checkout for free users upgrading, Portal for paid users.
 * Returns null when the card has no paid checkout tier (use link navigation).
 */
export function resolvePricingCardPaidAction(
  subscriptionTier: string | undefined | null,
  checkoutTier: CheckoutTier | undefined
): PricingCardPaidAction | null {
  if (!checkoutTier) {
    return null;
  }

  if (isFreeSubscriptionTier(subscriptionTier)) {
    return 'checkout';
  }

  return 'portal';
}
