// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

vi.mock('@/services/auth', async (importOriginal) => {
  const actual = await importOriginal();

  return {
    ...(actual as Record<string, unknown>),
    refreshToken: vi.fn(),
    handleSessionExpired: vi.fn(),
    getCsrfToken: vi.fn(() => 'csrf-token'),
  };
});

vi.mock('@/utils/app-events', () => ({
  dispatchSessionExpired: vi.fn(),
}));

describe('automatic token refresh', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    vi.clearAllMocks();
  });

  afterEach(async () => {
    global.fetch = originalFetch;
    const auth = await import('@/services/auth');

    vi.mocked(auth.getCsrfToken).mockImplementation(() => 'csrf-token');
  });

  describe('refreshTokenIfNeeded', () => {
    it('returns true when refresh endpoint succeeds', async () => {
      const { refreshTokenIfNeeded } = await import('@/services/api');
      const { refreshToken: mockRefreshToken } = await import('@/services/auth');

      (mockRefreshToken as Mock).mockResolvedValueOnce({ data: {} });

      const result = await refreshTokenIfNeeded();

      expect(result).toBe(true);
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
    });

    // A DEPLOY IS NOT AN EXPIRY (286b80368). This used to be one test asserting that ANY refresh
    // failure expires the session — the behaviour that logged users out on every push to master,
    // because the proactive timer fires 90s before expiry and collides with the container swap.
    // `isTransientTransportError` now splits the two cases, so the contract needs two tests: one
    // for "the server never answered" and one for "the server said no". Keeping only the first
    // would leave the real expiry path unpinned, which is how the opposite bug ships next.
    it('returns false and KEEPS the session when refresh never reached the server', async () => {
      vi.useFakeTimers();

      try {
        const { refreshTokenIfNeeded } = await import('@/services/api');
        const { refreshToken: mockRefreshToken } = await import('@/services/auth');
        const { handleSessionExpired } = await import('@/services/auth');

        // No `status` — a network failure or an aborted request, exactly the shape a container
        // swap produces. It tells us nothing about whether the refresh cookie is still valid.
        (mockRefreshToken as Mock).mockRejectedValueOnce(new Error('refresh failed'));

        const result = await refreshTokenIfNeeded();

        expect(result).toBe(false);
        expect(handleSessionExpired).not.toHaveBeenCalled();
      } finally {
        vi.useRealTimers();
      }
    });

    it('returns false and expires the session when the server rejects the refresh cookie', async () => {
      const { refreshTokenIfNeeded } = await import('@/services/api');
      const { refreshToken: mockRefreshToken } = await import('@/services/auth');
      const { handleSessionExpired } = await import('@/services/auth');

      // 401 from /auth/refresh is the server understanding us and saying no.
      (mockRefreshToken as Mock).mockRejectedValueOnce(
        Object.assign(new Error('refresh rejected'), { status: 401 })
      );

      const result = await refreshTokenIfNeeded();

      expect(result).toBe(false);
      expect(handleSessionExpired).toHaveBeenCalledTimes(1);
    });
  });

  describe('concurrent refresh handling', () => {
    it('should only perform one refresh for multiple concurrent calls', async () => {
      const { refreshTokenIfNeeded } = await import('@/services/api');
      const { refreshToken: mockRefreshToken } = await import('@/services/auth');

      // Simulate slow refresh (100ms)
      (mockRefreshToken as Mock).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  data: {
                    access_token: 'new-token',
                    refresh_token: 'new-refresh',
                    expires_in: 1800,
                  },
                }),
              100
            )
          )
      );

      // Fire multiple concurrent refresh attempts
      const results = await Promise.all([
        refreshTokenIfNeeded(),
        refreshTokenIfNeeded(),
        refreshTokenIfNeeded(),
      ]);

      // All should succeed
      expect(results).toEqual([true, true, true]);

      // But only one refresh call should have been made
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
    });
  });

  describe('authenticatedFetch with auto-refresh', () => {
    // authenticatedFetch short-circuits with a synthetic 401 in server contexts
    // (typeof window === 'undefined'). These tests exercise the full browser-side
    // cookie-auth + reactive-refresh path, so we simulate a browser environment.
    beforeEach(() => {
      (globalThis as unknown as Record<string, unknown>)['window'] = {};
    });

    afterEach(() => {
      // @ts-expect-error — restoring the deleted window to avoid leaking state
      delete globalThis.window;
    });

    it('retries once after 401 when refresh succeeds', async () => {
      const { authenticatedFetch } = await import('@/services/api');
      const { refreshToken: mockRefreshToken } = await import('@/services/auth');

      mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200 });
      (mockRefreshToken as Mock).mockResolvedValueOnce({ data: {} });

      const response = await authenticatedFetch('/api/test');

      expect(response.status).toBe(200);
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('after 401 refresh, retry PATCH sends fresh X-CSRF-Token (matches rotated pulsai_csrf)', async () => {
      const auth = await import('@/services/auth');
      const getCsrf = vi.mocked(auth.getCsrfToken);

      getCsrf.mockReset();
      // Mocked refreshToken does not call getCsrfToken — only initial headers + post-refresh update.
      getCsrf.mockReturnValueOnce('csrf-before-refresh').mockReturnValueOnce('csrf-after-refresh');

      const { authenticatedFetch } = await import('@/services/api');
      const { refreshToken: mockRefreshToken } = await import('@/services/auth');

      mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200 });
      (mockRefreshToken as Mock).mockResolvedValueOnce({ data: {} });

      await authenticatedFetch('/api/test', {
        method: 'PATCH',
        body: JSON.stringify({ x: 1 }),
      });

      expect(mockFetch).toHaveBeenCalledTimes(2);
      // Same Headers instance is reused and updated before retry; assert token reads instead.
      expect(getCsrf.mock.calls).toHaveLength(2);
      expect(getCsrf.mock.results[0]?.value).toBe('csrf-before-refresh');
      expect(getCsrf.mock.results[1]?.value).toBe('csrf-after-refresh');
      const retryInit = mockFetch.mock.calls[1]?.[1];

      expect(retryInit).toBeDefined();
      expect((retryInit?.headers as Headers).get('X-CSRF-Token')).toBe('csrf-after-refresh');
    });

    it('sends credentials include and csrf header for mutating requests', async () => {
      const { authenticatedFetch } = await import('@/services/api');

      mockFetch.mockResolvedValueOnce({ ok: true, status: 200 });

      await authenticatedFetch('/api/test', {
        method: 'POST',
        body: JSON.stringify({ hello: 'world' }),
      });
      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = callArgs[1].headers as Headers;

      expect(callArgs[1].credentials).toBe('include');
      expect(headers.get('X-CSRF-Token')).toBe('csrf-token');
    });

    it('throws sessionExpired and does not retry forever when refresh fails', async () => {
      const { authenticatedFetch } = await import('@/services/api');
      const { refreshToken: mockRefreshToken } = await import('@/services/auth');
      const { handleSessionExpired } = await import('@/services/auth');

      mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });
      (mockRefreshToken as Mock).mockRejectedValueOnce(new Error('Refresh failed'));

      await expect(authenticatedFetch('/api/test')).rejects.toThrow('sessionExpired');

      expect(handleSessionExpired).toHaveBeenCalled();
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  describe('awaitPendingTokenRefresh', () => {
    it('resolves immediately when no refresh is in progress', async () => {
      const { awaitPendingTokenRefresh } = await import('@/services/api');

      await expect(awaitPendingTokenRefresh()).resolves.toBeUndefined();
    });
  });
});
