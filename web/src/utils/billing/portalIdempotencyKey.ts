import {
  clearBillingSessionIdempotencyKey,
  resolveBillingSessionIdempotencyKey,
} from '@/utils/billing/billingSessionIdempotencyKey';

const STORAGE_KEY = 'pulsai:billing:portal-idem';

/**
 * Stable Idempotency-Key for portal opens (double-click / retry after network drop).
 */
export function resolveBillingPortalIdempotencyKey(): string {
  return resolveBillingSessionIdempotencyKey(STORAGE_KEY);
}

/** Call when user returns from Stripe Customer Portal (billing settings mount). */
export function clearBillingPortalIdempotencyKey(): void {
  clearBillingSessionIdempotencyKey(STORAGE_KEY);
}
