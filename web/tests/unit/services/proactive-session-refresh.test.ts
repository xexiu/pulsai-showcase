/**
 * Proactive access refresh — schedule refresh before cookie access TTL to reduce 401-first-leg noise.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const refreshTokenMock = vi.fn();

vi.mock('@/services/auth', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;

  return {
    ...actual,
    refreshToken: (...args: unknown[]) => refreshTokenMock(...args),
    handleSessionExpired: vi.fn(),
  };
});

describe('a deploy is not an expiry', () => {
  /**
   * Owner, 2026-09-08, with a screenshot: "why everytime you push to master, railways start
   * deploy and then I get the login page saying 'Session expirada'".
   *
   * The proactive timer fires 90s before access expiry, so a Railway container swap reliably
   * lands the refresh POST on a 502 or a dead socket. The catch expired the session for it.
   */
  beforeEach(() => {
    vi.useFakeTimers();
    refreshTokenMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does NOT expire the session when the API is mid-deploy', async () => {
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');
    const { handleSessionExpired } = await import('@/services/auth');

    refreshTokenMock.mockRejectedValueOnce(
      Object.assign(new Error('Bad Gateway'), { status: 502 })
    );

    await expect(refreshSessionAndReschedule()).resolves.toBe(false);
    expect(handleSessionExpired).not.toHaveBeenCalled();
  });

  it('does NOT expire the session on a bare network failure', async () => {
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');
    const { handleSessionExpired } = await import('@/services/auth');

    refreshTokenMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(refreshSessionAndReschedule()).resolves.toBe(false);
    expect(handleSessionExpired).not.toHaveBeenCalled();
  });

  it('re-arms the timer after a transient failure, so the session does not die quietly', async () => {
    // Without a reschedule the timer is gone and nothing refreshes again -- the session would
    // expire at TTL instead of now, which is a worse bug wearing a fix.
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');

    refreshTokenMock.mockRejectedValueOnce(Object.assign(new Error('down'), { status: 503 }));
    await refreshSessionAndReschedule();

    refreshTokenMock.mockResolvedValueOnce({ data: { expires_in: 900 } });
    await vi.advanceTimersByTimeAsync(5_000);

    expect(refreshTokenMock).toHaveBeenCalledTimes(2);
  });

  it('STILL expires the session when the refresh cookie is genuinely dead', async () => {
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');
    const { handleSessionExpired } = await import('@/services/auth');

    refreshTokenMock.mockRejectedValueOnce(
      Object.assign(new Error('Unauthorized'), { status: 401 })
    );

    await expect(refreshSessionAndReschedule()).resolves.toBe(false);
    expect(handleSessionExpired).toHaveBeenCalled();
  });
});

describe('proactive-session-refresh', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();
    refreshTokenMock.mockReset();
    refreshTokenMock.mockResolvedValue({
      data: {
        access_token: 'a',
        refresh_token: 'r',
        token_type: 'bearer',
        expires_in: 120,
      },
    });
  });

  afterEach(async () => {
    vi.useRealTimers();
    const { clearProactiveAccessRefreshSchedule } =
      await import('@/services/proactive-session-refresh');

    clearProactiveAccessRefreshSchedule();
  });

  it('clears prior timer when rescheduling', async () => {
    const { scheduleProactiveAccessRefreshFromExpiresIn, clearProactiveAccessRefreshSchedule } =
      await import('@/services/proactive-session-refresh');

    scheduleProactiveAccessRefreshFromExpiresIn(600);
    scheduleProactiveAccessRefreshFromExpiresIn(600);

    clearProactiveAccessRefreshSchedule();

    await vi.advanceTimersByTimeAsync(10 * 60 * 1000);
    expect(refreshTokenMock).not.toHaveBeenCalled();
  });

  it('fires refreshToken shortly before expiry (lead window)', async () => {
    const { scheduleProactiveAccessRefreshFromExpiresIn } =
      await import('@/services/proactive-session-refresh');

    scheduleProactiveAccessRefreshFromExpiresIn(200);

    await vi.advanceTimersByTimeAsync(109_999);
    expect(refreshTokenMock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(refreshTokenMock).toHaveBeenCalledTimes(1);
  });

  it('chains next schedule from refresh response expires_in', async () => {
    const { scheduleProactiveAccessRefreshFromExpiresIn } =
      await import('@/services/proactive-session-refresh');

    scheduleProactiveAccessRefreshFromExpiresIn(200);
    await vi.advanceTimersByTimeAsync(110_000);

    expect(refreshTokenMock).toHaveBeenCalledTimes(1);
    refreshTokenMock.mockClear();

    await vi.advanceTimersByTimeAsync(29_999);
    expect(refreshTokenMock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(refreshTokenMock).toHaveBeenCalledTimes(1);
  });

  it('no-ops for non-positive expires_in', async () => {
    const { scheduleProactiveAccessRefreshFromExpiresIn } =
      await import('@/services/proactive-session-refresh');

    scheduleProactiveAccessRefreshFromExpiresIn(0);
    scheduleProactiveAccessRefreshFromExpiresIn(-10);

    await vi.advanceTimersByTimeAsync(60 * 60 * 1000);
    expect(refreshTokenMock).not.toHaveBeenCalled();
  });

  it('does not expire session when refresh fails with IP_BLOCKED', async () => {
    const { AuthError, handleSessionExpired } = await import('@/services/auth');
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');

    refreshTokenMock.mockRejectedValueOnce(
      new AuthError('Access from this network is temporarily restricted.', 'IP_BLOCKED', 403)
    );

    await expect(refreshSessionAndReschedule()).rejects.toMatchObject({ code: 'IP_BLOCKED' });
    expect(handleSessionExpired).not.toHaveBeenCalled();
  });
});
