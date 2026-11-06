/**
 * "The server said no" and "the server did not answer" are different facts.
 *
 * Owner, 2026-09-08, with a screenshot of the login page: "Why everytime you push to master,
 * railways start deploy and then I get the login page saying 'Session expirada..' and I need to
 * log in again... Is that an architect decission/approach? who made that and why?"
 *
 * Nobody chose it. `refreshSessionAndReschedule` caught EVERY error, exempted only IP_BLOCKED,
 * and called `handleSessionExpired()` for the rest. The proactive timer fires 90s before access
 * expiry, so a Railway container swap lands a `POST /auth/refresh` on a 502 or a dead socket and
 * the user is thrown to the login page with perfectly valid cookies.
 *
 * The JWT secret is NOT the cause and was ruled out first: `secret_key` defaults to a fixed
 * constant and `settings.py` REFUSES that default in production, so prod signs with a stable env
 * secret and tokens survive a restart.
 *
 * REUSE-AUDIT: modelled on `is-ip-blocked-error.ts` -- same folder, same duck-typed predicate
 * shape, same reason for existing (a refresh failure that does not mean the session is dead).
 * Not extended into that file: it answers "is this the IP blocklist", a different question with
 * a different answer, and one predicate returning true for two unrelated causes cannot be read
 * at the call site.
 */

import { describe, expect, it } from 'vitest';

import { isTransientTransportError } from '@/services/auth/is-transient-transport-error';

describe('the size of the exemption, which is the fix expressed as a number', () => {
  /**
   * BEFORE `286b80368`, `refreshSessionAndReschedule` expired the session on ANY refresh failure
   * with exactly ONE exemption (IP_BLOCKED). So of the 200 HTTP statuses in 400-599, the number
   * that could reach the user as anything other than "Sesión expirada" was ZERO.
   *
   * This test measures the AFTER, rather than asserting it in prose: it sweeps the whole 400-599
   * range through the shipped predicate and counts. It is a ratchet on the surface, not a
   * restatement of the implementation -- shrink the exemption and this fails with the new number.
   */
  it('keeps the session for 102 of the 200 statuses in 400-599, and expired it for 0 before', () => {
    const kept: number[] = [];

    for (let status = 400; status <= 599; status += 1) {
      if (isTransientTransportError({ status })) {
        kept.push(status);
      }
    }

    // 100 server-side (500-599) plus the two 4xx that mean "later, not never".
    expect(kept).toHaveLength(102);
    expect(kept).toContain(502); // the container swap that logged everyone out on deploy
    expect(kept).toContain(408);
    expect(kept).toContain(429);

    // A genuine rejection is still a rejection -- the fix must not have blunted that.
    expect(kept).not.toContain(401);
    expect(kept).not.toContain(403);
  });

  it('keeps the session when the request never reached a server at all', () => {
    // A bare fetch TypeError carries no status; it is the deploy window's other shape.
    expect(isTransientTransportError(new TypeError('Failed to fetch'))).toBe(true);
  });
});

describe('isTransientTransportError', () => {
  describe('the server never answered', () => {
    it('treats a fetch network failure as transient', () => {
      // What `fetch` rejects with when the container is mid-swap: a TypeError, no status.
      expect(isTransientTransportError(new TypeError('Failed to fetch'))).toBe(true);
    });

    it('treats an error with no numeric status as transient', () => {
      expect(isTransientTransportError({ message: 'network down' })).toBe(true);
    });

    it('treats status 0 as transient', () => {
      expect(isTransientTransportError({ status: 0 })).toBe(true);
    });
  });

  describe('the server answered that it is broken or busy', () => {
    it.each([500, 502, 503, 504])('treats %i as transient', (status) => {
      expect(isTransientTransportError({ status })).toBe(true);
    });

    it('treats 408 request timeout as transient', () => {
      expect(isTransientTransportError({ status: 408 })).toBe(true);
    });

    it('treats 429 as transient', () => {
      // Rate limiting is "come back later", never "your refresh token is dead".
      expect(isTransientTransportError({ status: 429 })).toBe(true);
    });
  });

  describe('the server answered that WE are wrong', () => {
    it.each([400, 401, 403, 404, 422])('does NOT treat %i as transient', (status) => {
      // 401 from /auth/refresh is the real thing: the refresh cookie is dead, expire the session.
      expect(isTransientTransportError({ status })).toBe(false);
    });
  });

  describe('it never throws on junk', () => {
    it.each([null, undefined, 'a string', 42])('handles %p', (value) => {
      expect(isTransientTransportError(value)).toBe(false);
    });

    it('handles a non-numeric status without treating it as a rejection', () => {
      // A string status is not evidence the server rejected us, so it reads as "unknown".
      expect(isTransientTransportError({ status: 'oops' })).toBe(true);
    });
  });
});
