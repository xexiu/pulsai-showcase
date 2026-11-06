/**
 * Billing settings UI — stable ids and checkout iteration (SoT).
 *
 * WHY separate from page: reuse in hooks (scroll) and molecules (section id) without duplication.
 */

import type { CheckoutTier } from '@/config/queryFetchersBilling';

/** DOM id for upgrade block — deep-link scroll from ?highlight= */
export const BILLING_UPGRADE_SECTION_ID = 'billing-upgrade-section';

/** @deprecated Use `BILLING_URL_QUERY_KEYS.highlight` or `readBillingUrlQueryParam`. */

/** Paid tiers available for Stripe Checkout (order = button order on page). */
export const CHECKOUT_TIERS: readonly CheckoutTier[] = ['starter', 'pro', 'elite'];

/** settingsBilling keys for upgrade CTA labels (must match messages JSON). */
export const CHECKOUT_TIER_LABEL_KEYS: Record<CheckoutTier, string> = {
  starter: 'upgradeStarter',
  pro: 'upgradePro',
  elite: 'upgradeElite',
};

/** settingsBilling namespace keys for known subscription_tier values from API */
export const SUBSCRIPTION_TIER_I18N_KEYS = {
  free: 'tierFree',
  starter: 'tierStarter',
  pro: 'tierPro',
  elite: 'tierElite',
} as const;

export type KnownSubscriptionTierKey = keyof typeof SUBSCRIPTION_TIER_I18N_KEYS;
