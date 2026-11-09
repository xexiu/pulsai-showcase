// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { defaultPaidSyncTierForUser } from '@/utils/admin/default-paid-sync-tier';
import { SUBSCRIPTION_TIERS } from '@/utils/constants';

describe('defaultPaidSyncTierForUser', () => {
  it('returns same tier for paid tiers', () => {
    expect(defaultPaidSyncTierForUser(SUBSCRIPTION_TIERS.STARTER)).toBe(SUBSCRIPTION_TIERS.STARTER);
    expect(defaultPaidSyncTierForUser(SUBSCRIPTION_TIERS.PRO)).toBe(SUBSCRIPTION_TIERS.PRO);
    expect(defaultPaidSyncTierForUser(SUBSCRIPTION_TIERS.ELITE)).toBe(SUBSCRIPTION_TIERS.ELITE);
  });

  it('defaults free to starter', () => {
    expect(defaultPaidSyncTierForUser(SUBSCRIPTION_TIERS.FREE)).toBe(SUBSCRIPTION_TIERS.STARTER);
  });

  it('defaults unknown tier string to starter', () => {
    expect(defaultPaidSyncTierForUser('unknown')).toBe(SUBSCRIPTION_TIERS.STARTER);
  });
});
