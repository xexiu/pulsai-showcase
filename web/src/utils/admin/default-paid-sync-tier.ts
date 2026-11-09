/**
 * Default Stripe sync target tier from the user's current DB tier (paid tiers only).
 */

import { SUBSCRIPTION_TIERS } from '@/utils/constants';

export function defaultPaidSyncTierForUser(subscriptionTier: string): string {
  if (
    subscriptionTier === SUBSCRIPTION_TIERS.STARTER ||
    subscriptionTier === SUBSCRIPTION_TIERS.PRO ||
    subscriptionTier === SUBSCRIPTION_TIERS.ELITE
  ) {
    return subscriptionTier;
  }

  return SUBSCRIPTION_TIERS.STARTER;
}
