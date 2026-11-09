/**
 * Exchange permission helpers — shared logic for connections list and card.
 *
 * §2 CODING_STANDARDS: DRY — single source of truth for permission checks.
 */

import type { ExchangePermissionKey } from '@/types/tradingBarrel';
import { EXCHANGE_PERMISSION_KEYS } from '@/utils/constants/trading';

/** Returns only the permission keys that are `true` in the permissions object. */
export function getGrantedPermissions(
  permissions: Record<string, unknown>
): ExchangePermissionKey[] {
  return EXCHANGE_PERMISSION_KEYS.filter((k) => permissions[k] === true);
}

/** True when the key has at least one permission but no `trade` permission. */
export function isReadOnly(permissions: Record<string, unknown>): boolean {
  const granted = getGrantedPermissions(permissions);

  return granted.length > 0 && !granted.includes('trade');
}
