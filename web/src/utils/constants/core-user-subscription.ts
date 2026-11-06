/**
 * User roles, subscription tiers, plan caps (SoT for entitlements UI).
 * Split from core.ts — keep sections ≤400 lines per CODING_STANDARDS.
 */

// ============================================================================
// User/Auth Constants
// ============================================================================

export const USER_ROLES = {
  SUPER_ADMIN: 'super_admin',
  ADMIN: 'admin',
  USER: 'user',
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

/**
 * True when the role has staff-level access (admin or super_admin).
 *
 * WHY it lives here: this exact expression was written out inline in **8 places**, including
 * two private helpers (`isStaff` in trading-tier-policy, `isAdminRole` in
 * useFullChartModelOverlay) that were byte-identical to each other. Adding a role, or deciding
 * a role is no longer staff, would have had to find all eight — and missing one silently grants
 * or denies access rather than failing.
 *
 * Mirrors the backend `STAFF_ROLES` in `apps/api/src/domain/enums.py`, which is itself pinned
 * against `UserRole.is_admin()` by `apps/api/tests/domain/test_staff_roles_sot.py`.
 *
 * NOT for super_admin-only checks — those are a stricter, deliberately different predicate
 * (role management, destructive user actions) and must keep comparing to `SUPER_ADMIN` alone.
 *
 * @param role - Role string from the profile/user payload; `undefined` is not staff.
 */
export function isStaffRole(role: UserRole | string | undefined | null): boolean {
  return role === USER_ROLES.ADMIN || role === USER_ROLES.SUPER_ADMIN;
}

export const SUBSCRIPTION_TIERS = {
  FREE: 'free',
  STARTER: 'starter',
  PRO: 'pro',
  ELITE: 'elite',
} as const;

export type SubscriptionTier = (typeof SUBSCRIPTION_TIERS)[keyof typeof SUBSCRIPTION_TIERS];

/**
 * Full-chart indicator entitlement caps (SoT for FE plan gating).
 *
 * WHY centralized:
 * - Avoid magic numbers in entitlement helpers/components.
 * - Keep one place to audit plan policy changes.
 *
 * POLICY:
 * - free: 3
 * - starter: 5
 * - pro: 10
 * - elite/admin/super_admin: unlimited
 */
export const CHART_INDICATOR_LIMITS = {
  /**
   * Owner, 2026-09-14: "can we move up to 3 default indicators limits for guest and fress users?"
   * Raised from 2 so the two always-free indicators (Stochastic, Green/Red zone) leave a viewer one
   * slot of their own rather than consuming the entire allowance.
   *
   * MIRROR: `resolve_chart_indicator_limit` in apps/api/src/application/auth/
   * subscription_entitlements.py serves the 403 that gates this. The two must agree — a lower
   * server value makes the UI promise a slot the API refuses.
   */
  FREE: 3,
  STARTER: 5,
  PRO: 10,
  UNLIMITED: null,
} as const;
