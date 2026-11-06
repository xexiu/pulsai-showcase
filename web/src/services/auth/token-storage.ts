/**
 * Token-storage compatibility shims.
 *
 * The current auth surface is **HttpOnly cookie only** — there is no
 * client-side token persistence. These functions remain as no-op shims
 * for call-site compatibility with legacy code that hasn't migrated yet,
 * plus the ``clearTokens`` hygiene step that wipes pre-cookie storage
 * keys.
 */

import type { StoredTokens } from '@/services/auth/internals';

/**
 * Legacy storage keys from older (pre-cookie-auth) implementations.
 * The session-storage variant was only ever written for ``_tokens`` —
 * the ``_storage`` slot is local-only.
 */
const LEGACY_LOCAL_STORAGE_KEYS = ['pulsai_auth_tokens', 'pulsai_auth_storage'] as const;
const LEGACY_SESSION_STORAGE_KEYS = ['pulsai_auth_tokens'] as const;

export function clearTokens(): void {
  if (typeof window === 'undefined') {
    return;
  }
  for (const key of LEGACY_LOCAL_STORAGE_KEYS) {
    localStorage.removeItem(key);
  }
  for (const key of LEGACY_SESSION_STORAGE_KEYS) {
    sessionStorage.removeItem(key);
  }
}

export function saveTokens(_tokens: StoredTokens, _rememberMe = true): void {
  // Cookie-auth mode does not persist tokens in Web Storage.
}

export function getStoredTokens(): StoredTokens | null {
  return null;
}
