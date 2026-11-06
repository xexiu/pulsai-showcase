import type { BillingCurrency, CheckoutTier } from '@/types/billing-api';
import {
  clearBillingSessionIdempotencyKey,
  clearBillingSessionIdempotencyKeysByPrefix,
  resolveBillingSessionIdempotencyKey,
} from '@/utils/billing/billingSessionIdempotencyKey';

const STORAGE_PREFIX = 'pulsai:billing:checkout-idem:';

function storageKey(tier: CheckoutTier, currency: BillingCurrency): string {
  return `${STORAGE_PREFIX}${tier}:${currency}`;
}

/**
 * Stable Idempotency-Key per checkout intent (tier + currency) for retry after network drops.
 */
export function resolveBillingCheckoutIdempotencyKey(
  tier: CheckoutTier,
  currency: BillingCurrency
): string {
  return resolveBillingSessionIdempotencyKey(storageKey(tier, currency));
}

/** Call after successful redirect to Stripe or confirmed checkout completion. */
export function clearBillingCheckoutIdempotencyKey(
  tier: CheckoutTier,
  currency: BillingCurrency
): void {
  clearBillingSessionIdempotencyKey(storageKey(tier, currency));
}

/** Clears all stored checkout idempotency keys (e.g. after Stripe success redirect). */
export function clearAllBillingCheckoutIdempotencyKeys(): void {
  clearBillingSessionIdempotencyKeysByPrefix(STORAGE_PREFIX);
}
