/**
 * Maps backend subscription_tier string to settingsBilling translation keys.
 */

import {
  type KnownSubscriptionTierKey,
  SUBSCRIPTION_TIER_I18N_KEYS,
} from '@/utils/constants/billing-settings';

export function getSubscriptionTierDisplayName(
  tier: string,
  translate: (key: string) => string
): string {
  const key = SUBSCRIPTION_TIER_I18N_KEYS[tier as KnownSubscriptionTierKey];

  if (key !== undefined) {
    return translate(key);
  }

  return tier;
}
