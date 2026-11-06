/**
 * `isStaffRole` — the one definition of "does this role have staff access".
 *
 * This expression was written out inline in 8 places, two of them private helpers
 * (`isStaff` in trading-tier-policy, `isAdminRole` in useFullChartModelOverlay) that were
 * byte-identical to each other. Adding a role, or deciding one is no longer staff, would have
 * had to find all eight — and a missed site silently grants or denies access instead of failing.
 *
 * The negative cases matter more than the positive ones here: this predicate unlocks unlimited
 * chart indicators, unlimited trading symbol slots, every timeframe, and the admin nav link.
 */

import { describe, expect, it } from 'vitest';

import { USER_ROLES, isStaffRole } from '@/utils/constants/core-user-subscription';

describe('isStaffRole', () => {
  it('accepts admin and super_admin', () => {
    expect(isStaffRole(USER_ROLES.ADMIN)).toBe(true);
    expect(isStaffRole(USER_ROLES.SUPER_ADMIN)).toBe(true);
  });

  it('rejects the ordinary user role', () => {
    expect(isStaffRole(USER_ROLES.USER)).toBe(false);
  });

  it('rejects absent roles rather than throwing', () => {
    // Profile payloads type `role` as optional, so every call site can hand over undefined/null.
    expect(isStaffRole(undefined)).toBe(false);
    expect(isStaffRole(null)).toBe(false);
    expect(isStaffRole('')).toBe(false);
  });

  it('is exact — no case-insensitive or partial matching', () => {
    // The wire value is lowercase by contract (BE `STAFF_ROLES`). If that ever changes, this
    // should fail loudly rather than a call site quietly deciding an admin is not staff.
    expect(isStaffRole('ADMIN')).toBe(false);
    expect(isStaffRole('Admin')).toBe(false);
    expect(isStaffRole('super-admin')).toBe(false);
    expect(isStaffRole('administrator')).toBe(false);
  });

  it('covers every role the constant declares, so a NEW role cannot be forgotten', () => {
    // Guard the guard: without this, adding USER_ROLES.SUPPORT would leave isStaffRole
    // unreviewed and every assertion above would still pass.
    const decided = Object.values(USER_ROLES).map((role) => [role, isStaffRole(role)] as const);

    expect(decided).toEqual([
      [USER_ROLES.SUPER_ADMIN, true],
      [USER_ROLES.ADMIN, true],
      [USER_ROLES.USER, false],
    ]);
  });
});
