import {
  SUBSCRIPTION_TIERS,
  USER_ROLES,
  type SubscriptionTier,
  type UserRole,
} from '@/utils/constants';

const REDUCED_SIGNAL_TIERS = new Set<string>([SUBSCRIPTION_TIERS.FREE, SUBSCRIPTION_TIERS.STARTER]);
const ZERO_DELAY_SIGNAL_TIERS = new Set<string>([SUBSCRIPTION_TIERS.PRO, SUBSCRIPTION_TIERS.ELITE]);
const ZERO_DELAY_ROLES = new Set<string>([USER_ROLES.ADMIN, USER_ROLES.SUPER_ADMIN]);

export type SignalTierPolicyInput = {
  subscriptionTier?: SubscriptionTier | string;
  userRole?: UserRole | string;
};

export function normalizePolicyValue(value: string | undefined): string | null {
  if (value == null) {
    return null;
  }

  return value.toString().trim().toLowerCase();
}

export function isReducedSignalTier(tier: SubscriptionTier | string | undefined): boolean {
  const normalizedTier = normalizePolicyValue(tier);

  if (normalizedTier == null) {
    return false;
  }

  return REDUCED_SIGNAL_TIERS.has(normalizedTier);
}

export function hasZeroDelaySignalAccess({
  subscriptionTier,
  userRole,
}: SignalTierPolicyInput): boolean {
  const normalizedRole = normalizePolicyValue(userRole);

  if (normalizedRole != null && ZERO_DELAY_ROLES.has(normalizedRole)) {
    return true;
  }

  const normalizedTier = normalizePolicyValue(subscriptionTier);

  if (normalizedTier == null) {
    return true;
  }

  return ZERO_DELAY_SIGNAL_TIERS.has(normalizedTier);
}
