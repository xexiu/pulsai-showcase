'use client';

import { useEffect, type ReactNode } from 'react';

import { clearBillingPortalIdempotencyKey } from '@/utils/billing/portalIdempotencyKey';

/**
 * Clears portal idempotency key when user lands on billing settings (Stripe portal return URL).
 */
export function BillingPortalReturnCleanup(): ReactNode {
  useEffect(() => {
    clearBillingPortalIdempotencyKey();
  }, []);

  return null;
}
