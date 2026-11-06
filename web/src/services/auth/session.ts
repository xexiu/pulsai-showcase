/**
 * Authenticated session endpoints + session-lifecycle helpers:
 *   - ``logout``        — invalidate tokens server-side
 *   - ``getCurrentUser`` — read the active profile (auto-recovers from 401)
 *   - ``handleSessionExpired`` — clear local state and notify the UI
 *   - ``isTokenExpired``       — local expiry check with 30s safety buffer
 */

import { refreshToken } from '@/services/auth/credentials';
import { getCsrfToken } from '@/services/auth/csrf';
import { AuthError, authRequestUrl, handleResponse } from '@/services/auth/internals';
import { clearTokens } from '@/services/auth/token-storage';
import type { UserResponse } from '@/types/auth';
import { HTTP_STATUS } from '@/utils/constants';

const TOKEN_EXPIRY_BUFFER_SECONDS = 30;

/**
 * Logout (invalidate tokens server-side).
 */
export async function logout(_accessToken?: string, signal?: AbortSignal): Promise<void> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken;
  }
  const init: RequestInit = {
    method: 'POST',
    headers,
    credentials: 'include',
  };

  if (signal) {
    init.signal = signal;
  }
  const response = await fetch(authRequestUrl('/logout'), init);

  // 204 No Content is expected
  if (!response.ok && response.status !== HTTP_STATUS.NO_CONTENT) {
    throw new AuthError('Logout failed', 'LOGOUT_FAILED', response.status);
  }
}

/**
 * Get current user profile.
 *
 * Cookie-auth: if ``/me`` returns 401 (e.g. access cookie expired), refresh
 * once via ``/refresh`` then retry ``/me`` — same recovery path as
 * ``authenticatedFetch`` so sessions survive access TTL.
 */
export async function getCurrentUser(
  _accessToken?: string,
  signal?: AbortSignal
): Promise<UserResponse> {
  const meInit: RequestInit = {
    method: 'GET',
    credentials: 'include',
  };

  if (signal) {
    meInit.signal = signal;
  }

  let response = await fetch(authRequestUrl('/me'), meInit);

  if (response.status === HTTP_STATUS.UNAUTHORIZED) {
    await refreshToken(undefined, signal);
    response = await fetch(authRequestUrl('/me'), meInit);
  }

  return handleResponse<UserResponse>(response);
}

/**
 * Handle session expiration — clears tokens AND notifies AuthProvider.
 *
 * WHY SEPARATE FROM clearTokens()?
 * - clearTokens() is also called during normal logout
 * - We only want to dispatch event + show toast for UNEXPECTED expiration
 * - AuthProvider listens for this event to update isAuthenticated state
 *
 * Uses dynamic import to avoid circular dependency with app-events.
 */
export async function handleSessionExpired(): Promise<void> {
  clearTokens();

  if (typeof window === 'undefined') return;

  const { dispatchSessionExpired } = await import('@/utils/app-events');

  dispatchSessionExpired();
}

/**
 * Check if access token is expired (with safety buffer to avoid races).
 */
export function isTokenExpired(expiresAt: number): boolean {
  return Date.now() >= (expiresAt - TOKEN_EXPIRY_BUFFER_SECONDS) * 1000;
}
