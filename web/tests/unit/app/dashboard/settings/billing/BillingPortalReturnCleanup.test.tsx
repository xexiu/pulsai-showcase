import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { BillingPortalReturnCleanup } from '@/app/[locale]/dashboard/settings/billing/BillingPortalReturnCleanup';

const mockClearPortal = vi.fn();

vi.mock('@/utils/billing/portalIdempotencyKey', () => ({
  clearBillingPortalIdempotencyKey: () => mockClearPortal(),
}));

describe('BillingPortalReturnCleanup', () => {
  it('clears portal idempotency key on mount', () => {
    mockClearPortal.mockClear();

    render(<BillingPortalReturnCleanup />);

    expect(mockClearPortal).toHaveBeenCalledOnce();
  });
});
