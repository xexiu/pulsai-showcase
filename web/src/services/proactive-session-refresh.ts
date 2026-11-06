/**
 * Proactive session refresh — schedule POST /auth/refresh before HttpOnly access cookie expires.
 *
 * WHY: Reduces "401 → refresh → retry" on the next API call; DevTools still may log the first 401
 * occasionally if the tab is suspended or the timer is delayed.
 *
 * Cookie-auth: `expires_in` comes from login/refresh JSON (TokenData); not read from JWT in JS.
 *
 * @see refreshToken in `@/services/auth`
 * @see performRefresh in `@/services/api`
 */

import { handleSessionExpired, refreshToken } from '@/services/auth';
import { isIpBlockedError } from '@/services/auth/is-ip-blocked-error';
import { isTransientTransportError } from '@/services/auth/is-transient-transport-error';

/** Refresh this many seconds before access expiry (balance: fewer surprise 401s vs extra refresh calls). */
const PROACTIVE_REFRESH_LEAD_SECONDS = 90;

/** Avoid sub-second timer spam if TTL math is tight or misconfigured. */
const MIN_SCHEDULE_DELAY_MS = 5_000;

let timerId: ReturnType<typeof setTimeout> | null = null;

export function clearProactiveAccessRefreshSchedule(): void {
  if (timerId === null) {
    return;
  }

  clearTimeout(timerId);
  timerId = null;
}

/**
 * Schedule a single proactive refresh from access TTL (seconds), replacing any prior schedule.
 */
export function scheduleProactiveAccessRefreshFromExpiresIn(expiresInSeconds: number): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (!Number.isFinite(expiresInSeconds) || expiresInSeconds <= 0) {
    return;
  }

  const delaySec = Math.max(expiresInSeconds - PROACTIVE_REFRESH_LEAD_SECONDS, 1);

  armRefreshTimer(Math.max(delaySec * 1000, MIN_SCHEDULE_DELAY_MS));
}

/**
 * Arm the single refresh timer after ``delayMs``, replacing any prior schedule.
 *
 * Extracted so the retry-after-a-transient-failure path can ask for a DELAY without inventing a
 * fake ``expires_in`` to get one. The two callers know different things -- one has a TTL, the
 * other has "soon" -- and only the arming is common.
 */
function armRefreshTimer(delayMs: number): void {
  clearProactiveAccessRefreshSchedule();

  timerId = setTimeout(() => {
    timerId = null;
    void refreshSessionAndReschedule().catch(() => {
      /* IP block / unexpected — expired path already cleared session when applicable */
    });
  }, delayMs);
}

/**
 * POST /auth/refresh and schedule the next proactive run from `expires_in`.
 * Used by reactive 401 path (`performRefresh`) and by the proactive timer.
 *
 * IP_BLOCKED is rethrown (not session-expired): cookies may still be valid after the block TTL.
 */
export async function refreshSessionAndReschedule(): Promise<boolean> {
  try {
    const response = await refreshToken();
    const expiresIn = response?.data?.expires_in;

    if (typeof expiresIn === 'number' && expiresIn > 0) {
      scheduleProactiveAccessRefreshFromExpiresIn(expiresIn);
    }

    return true;
  } catch (err) {
    if (isIpBlockedError(err)) {
      throw err;
    }

    // A DEPLOY IS NOT AN EXPIRY. This catch used to expire the session on every error, so a
    // Railway container swap -- which the proactive timer reliably collides with, firing 90s
    // before access expiry -- threw the user to the login page holding valid cookies. Owner,
    // 2026-09-08, with the screenshot: "why everytime you push to master ... 'Session expirada'".
    //
    // Re-arm rather than give up: without a reschedule the timer is gone, nothing refreshes
    // again, and the session dies quietly at TTL instead of loudly now -- a worse bug wearing a
    // fix. MIN_SCHEDULE_DELAY_MS is reused as the retry delay; it is this module's existing floor
    // for "soon", so no second timing constant is invented.
    if (isTransientTransportError(err)) {
      armRefreshTimer(MIN_SCHEDULE_DELAY_MS);

      return false;
    }

    await handleSessionExpired();

    return false;
  }
}
