import { afterEach, describe, expect, it } from 'vitest';

import {
  clearBillingPortalIdempotencyKey,
  resolveBillingPortalIdempotencyKey,
} from '@/utils/billing/portalIdempotencyKey';

describe('portalIdempotencyKey', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('returns the same key on repeat portal resolve calls', () => {
    const first = resolveBillingPortalIdempotencyKey();
    const second = resolveBillingPortalIdempotencyKey();

    expect(second).toBe(first);
  });

  it('clear removes stored key so the next resolve is fresh', () => {
    const first = resolveBillingPortalIdempotencyKey();

    clearBillingPortalIdempotencyKey();

    const second = resolveBillingPortalIdempotencyKey();

    expect(second).not.toBe(first);
  });
});
