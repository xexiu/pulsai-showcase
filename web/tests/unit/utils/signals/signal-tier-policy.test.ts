// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  hasZeroDelaySignalAccess,
  isReducedSignalTier,
  normalizePolicyValue,
} from '@/utils/signals/signal-tier-policy';

describe('signal-tier-policy', () => {
  it('normalizes mixed-case values', () => {
    expect(normalizePolicyValue('  Pro  ')).toBe('pro');
  });

  it('detects reduced tiers for free/starter', () => {
    expect(isReducedSignalTier('free')).toBe(true);
    expect(isReducedSignalTier('starter')).toBe(true);
    expect(isReducedSignalTier('pro')).toBe(false);
  });

  it('grants zero-delay access for admin roles regardless of tier', () => {
    expect(
      hasZeroDelaySignalAccess({
        subscriptionTier: 'free',
        userRole: 'admin',
      })
    ).toBe(true);
  });
});
