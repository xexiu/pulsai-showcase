// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';

import { getSubscriptionTierDisplayName } from '@/utils/billing/subscriptionTierDisplayName';

describe('getSubscriptionTierDisplayName', () => {
  it('uses i18n key for known tiers', () => {
    const tr = vi.fn((key: string) => `translated:${key}`);

    expect(getSubscriptionTierDisplayName('pro', tr)).toBe('translated:tierPro');
    expect(tr).toHaveBeenCalledWith('tierPro');
  });

  it('returns raw tier for unknown values', () => {
    const tr = vi.fn();

    expect(getSubscriptionTierDisplayName('custom_tier', tr)).toBe('custom_tier');
    expect(tr).not.toHaveBeenCalled();
  });
});
