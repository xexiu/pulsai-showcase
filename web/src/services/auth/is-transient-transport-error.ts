/**
 * True when a failed auth call means "no answer", not "your session is dead".
 *
 * WHY: `refreshSessionAndReschedule` used to expire the session on ANY refresh failure, with a
 * single exemption for IP_BLOCKED. The proactive timer fires 90s before access expiry, so a
 * Railway container swap put a `POST /auth/refresh` on the wire exactly while the API was
 * restarting -- and the user landed on "Sesión expirada" holding perfectly valid cookies. Owner,
 * 2026-09-08: "Is that an architect decission/approach? who made that and why?" It was neither;
 * it was a catch that conflated a rejection with a failure to reach.
 *
 * The split is HTTP's own, not a set of numbers picked for this bug:
 *
 *   4xx  the server understood us and said no  -> the session really is dead, expire it
 *   5xx  the server failed to answer           -> unknown, keep the session and retry
 *   none the request never got there at all    -> unknown, keep the session and retry
 *
 * with two 4xx exceptions that are explicitly "later, not never": 408 Request Timeout and
 * 429 Too Many Requests. Neither says anything about the refresh cookie's validity.
 *
 * Uses `status` duck-typing rather than `instanceof AuthError`, matching the sibling
 * `isIpBlockedError` -- so Vitest module resets and mocks that re-bind AuthError still classify
 * correctly, and a bare `TypeError` from `fetch` (which has no status at all) is handled by the
 * same path.
 *
 * FAILS TOWARD KEEPING THE SESSION. An unrecognised shape reads as "unknown", because the cost of
 * the two mistakes is not symmetric: wrongly keeping a dead session costs one 401 on the next
 * call, which the reactive path already handles; wrongly expiring a live one throws the user out.
 */

/** RFC 9110 408: the server gave up waiting for the request, not on the credentials. */
const HTTP_REQUEST_TIMEOUT = 408;

/** RFC 6585 429: "slow down", which says nothing about whether the refresh cookie is valid. */
const HTTP_TOO_MANY_REQUESTS = 429;

/** 4xx codes that mean "try again later", not "you are not who you say you are". */
const RETRYABLE_CLIENT_STATUSES = new Set([HTTP_REQUEST_TIMEOUT, HTTP_TOO_MANY_REQUESTS]);

/** Below this, a status is not a server-side failure. */
const SERVER_ERROR_FLOOR = 500;

/** Below this, a status is not a client-side rejection (1xx/2xx/3xx never reach here as errors). */
const CLIENT_ERROR_FLOOR = 400;

export function isTransientTransportError(err: unknown): boolean {
  if (err === null || typeof err !== 'object') {
    return false;
  }

  const { status } = err as { status?: unknown };

  // No numeric status: a network failure, an aborted request, or an error shape we do not know.
  // We never reached the server, so it has told us nothing about the session.
  if (typeof status !== 'number') {
    return true;
  }

  if (status >= SERVER_ERROR_FLOOR) {
    return true;
  }

  if (RETRYABLE_CLIENT_STATUSES.has(status)) {
    return true;
  }

  // A real rejection (401/403 from /auth/refresh is the refresh cookie being dead).
  return status >= CLIENT_ERROR_FLOOR ? false : true;
}
