// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { BillingCheckoutConflictError } from '@/types/billing-api';
import { parseBillingCheckoutFailure } from '@/utils/billing/parseBillingCheckoutFailure';
import { HTTP_STATUS } from '@/utils/constants/extended';

describe('parseBillingCheckoutFailure', () => {
  it('returns BillingCheckoutConflictError on 409 with use_billing_portal', () => {
    const err = parseBillingCheckoutFailure(
      HTTP_STATUS.CONFLICT,
      {
        error: {
          message: 'Use the billing portal',
          details: { use_billing_portal: true },
        },
      },
      'fallback'
    );

    expect(err).toBeInstanceOf(BillingCheckoutConflictError);
    expect(err.message).toContain('billing portal');
  });

  it('returns generic Error on 409 without portal hint', () => {
    const err = parseBillingCheckoutFailure(
      HTTP_STATUS.CONFLICT,
      { error: { message: 'other conflict' } },
      'fallback'
    );

    expect(err).toBeInstanceOf(Error);
    expect(err).not.toBeInstanceOf(BillingCheckoutConflictError);
  });

  it('returns generic Error on non-409', () => {
    const err = parseBillingCheckoutFailure(400, { detail: 'bad tier' }, 'fallback');

    expect(err.message).toBe('bad tier');
  });
});
