import { refreshSessionAndReschedule } from '@/services/proactive-session-refresh';

/**
 * Shared promise to prevent concurrent refresh calls.
 * When multiple requests detect 401 simultaneously,
 * they all await the same refresh promise.
 */
let refreshPromise: Promise<boolean> | null = null;

/**
 * Wait for an in-flight cookie-auth refresh to finish (if any).
 *
 * WHY: `/auth/refresh` rotates `pulsai_csrf`. If logout (or another mutation) runs while a refresh
 * is still completing, JS may read the pre-rotation token while the cookie jar already has the new
 * value → CSRF 403 and HttpOnly cookies never cleared on logout.
 */
export async function awaitPendingTokenRefresh(): Promise<void> {
  if (!refreshPromise) {
    return;
  }

  try {
    await refreshPromise;
  } catch {
    /* Caller still proceeds; refresh failure does not block local cleanup paths */
  }
}

/**
 * Perform the actual token refresh (shared with proactive timer via {@link refreshSessionAndReschedule}).
 */
async function performRefresh(): Promise<boolean> {
  return refreshSessionAndReschedule();
}

/**
 * Refresh session cookies after 401.
 *
 * @returns true if refresh succeeded, false otherwise
 */
export async function refreshTokenIfNeeded(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}
