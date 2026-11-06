/**
 * True when a failed auth/API call is an IP blocklist reject (not a dead session).
 *
 * WHY: Refresh failures normally dispatch session-expired. IP_BLOCKED is temporary
 * Redis enforcement — cookies may still be valid once the block TTL ends.
 *
 * Uses ``code`` duck-typing (not ``instanceof``) so Vitest module resets / mocks
 * that re-bind ``AuthError`` still classify correctly.
 */

export function isIpBlockedError(err: unknown): boolean {
  if (err === null || typeof err !== 'object') {
    return false;
  }

  return (err as { code?: unknown }).code === 'IP_BLOCKED';
}
