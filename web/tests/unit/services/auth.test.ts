// =============================================================================
// Auth Service Tests - PRO/Architect Tests
// =============================================================================
//
// PRO TESTS FOCUS:
// - API communication patterns
// - Error handling (network, auth, validation)
// - Token storage lifecycle
// - Edge cases (expired tokens, invalid responses)
// =============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AuthError,
  clearTokens,
  getCsrfToken,
  getCurrentUser,
  getStoredTokens,
  isTokenExpired,
  login,
  logout,
  refreshToken,
  register,
  saveTokens,
} from '@/services/auth';

// =============================================================================
// Test Setup
// =============================================================================

describe('auth service', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    // Clear both storages (Remember Me feature uses both)
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  // ===========================================================================
  // Login Tests
  // ===========================================================================

  describe('login', () => {
    const validCredentials = { email: 'test@example.com', password: 'Password123' };
    const mockTokenResponse = {
      data: {
        access_token: 'access-token-123',
        refresh_token: 'refresh-token-456',
        token_type: 'bearer',
        expires_in: 900,
      },
      meta: { timestamp: '2026-01-26T00:00:00Z' },
    };

    it('sends correct request to login endpoint with remember_me true by default', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      });

      await login(validCredentials);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/login'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: validCredentials.email,
            password: validCredentials.password,
            remember_me: true,
          }),
        })
      );
    });

    it('sends remember_me false when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      });

      await login({ ...validCredentials, remember_me: false });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/login'),
        expect.objectContaining({
          body: JSON.stringify({
            email: validCredentials.email,
            password: validCredentials.password,
            remember_me: false,
          }),
        })
      );
    });

    it('returns token data on successful login', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      });

      const result = await login(validCredentials);

      expect(result.data.access_token).toBe('access-token-123');
      expect(result.data.refresh_token).toBe('refresh-token-456');
      expect(result.data.expires_in).toBe(900);
    });

    it('throws AuthError on invalid credentials (401)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () =>
          Promise.resolve({
            error: { code: 'INVALID_CREDENTIALS', message: 'Invalid email or password' },
            meta: { timestamp: '2026-01-26T00:00:00Z' },
          }),
      });

      await expect(login(validCredentials)).rejects.toMatchObject({
        message: 'Invalid email or password',
        code: 'INVALID_CREDENTIALS',
        status: 401,
      });
    });

    it('throws AuthError on rate limit (429)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: () =>
          Promise.resolve({
            error: { code: 'RATE_LIMITED', message: 'Too many attempts' },
            meta: { timestamp: '2026-01-26T00:00:00Z' },
          }),
      });

      await expect(login(validCredentials)).rejects.toMatchObject({
        status: 429,
      });
    });

    it('handles network errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(login(validCredentials)).rejects.toThrow();
    });

    it('handles malformed JSON response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      await expect(login(validCredentials)).rejects.toThrow(AuthError);
    });

    it('forwards AbortSignal when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      });
      const controller = new AbortController();

      await login(validCredentials, controller.signal);

      const init = mockFetch.mock.calls[0]?.[1] as RequestInit | undefined;

      expect(init?.signal).toBe(controller.signal);
    });
  });

  // ===========================================================================
  // Register Tests
  // ===========================================================================

  describe('register', () => {
    const validData = {
      email: 'new@example.com',
      password: 'Password123',
      name: 'Test User',
      terms_consent: true,
      data_processing_consent: true,
    };
    const mockRegisterResponse = {
      data: {
        id: 'user-123',
        email: 'new@example.com',
        name: 'Test User',
        subscription_tier: 'free',
      },
      meta: { timestamp: '2026-01-26T00:00:00Z' },
    };

    it('sends correct request to register endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      });

      await register(validData);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/register'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(validData),
        })
      );
    });

    it('returns user data on successful registration', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      });

      const result = await register(validData);

      expect(result.data.id).toBe('user-123');
      expect(result.data.email).toBe('new@example.com');
    });

    it('throws AuthError on duplicate email (409)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: () =>
          Promise.resolve({
            error: { code: 'EMAIL_EXISTS', message: 'Email already registered' },
            meta: { timestamp: '2026-01-26T00:00:00Z' },
          }),
      });

      await expect(register(validData)).rejects.toMatchObject({
        code: 'EMAIL_EXISTS',
        status: 409,
      });
    });

    it('throws AuthError on validation error (422)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({
            error: { code: 'VALIDATION_ERROR', message: 'Password too weak' },
            meta: { timestamp: '2026-01-26T00:00:00Z' },
          }),
      });

      await expect(register(validData)).rejects.toMatchObject({
        status: 422,
      });
    });

    it('registers without name (optional field)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            ...mockRegisterResponse,
            data: { ...mockRegisterResponse.data, name: null },
          }),
      });

      const result = await register({
        email: validData.email,
        password: validData.password,
        terms_consent: validData.terms_consent,
        data_processing_consent: validData.data_processing_consent,
      });

      expect(result.data.email).toBe('new@example.com');
    });

    it('forwards AbortSignal when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      });
      const controller = new AbortController();

      await register(validData, controller.signal);

      const init = mockFetch.mock.calls[0]?.[1] as RequestInit | undefined;

      expect(init?.signal).toBe(controller.signal);
    });
  });

  // ===========================================================================
  // Refresh Token Tests
  // ===========================================================================

  describe('refreshToken', () => {
    const mockRefreshResponse = {
      data: {
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        token_type: 'bearer',
        expires_in: 900,
      },
      meta: { timestamp: '2026-01-26T00:00:00Z' },
    };

    it('sends refresh token to refresh endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRefreshResponse),
      });

      await refreshToken('old-refresh-token');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/refresh'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ refresh_token: 'old-refresh-token' }),
        })
      );
    });

    it('returns new token pair on success', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRefreshResponse),
      });

      const result = await refreshToken('old-refresh-token');

      expect(result.data.access_token).toBe('new-access-token');
      expect(result.data.refresh_token).toBe('new-refresh-token');
    });

    it('throws AuthError on invalid refresh token (401)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () =>
          Promise.resolve({
            error: { code: 'INVALID_TOKEN', message: 'Invalid refresh token' },
            meta: { timestamp: '2026-01-26T00:00:00Z' },
          }),
      });

      await expect(refreshToken('invalid-token')).rejects.toMatchObject({
        code: 'INVALID_TOKEN',
        status: 401,
      });
    });

    it('sends X-CSRF-Token when pulsai_csrf cookie is present (cookie-auth refresh)', async () => {
      document.cookie = 'pulsai_csrf=test-csrf-value; path=/';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRefreshResponse),
      });

      await refreshToken();

      const init = mockFetch.mock.calls[0]?.[1] as RequestInit | undefined;
      const headers = init?.headers as Headers | undefined;

      expect(headers?.get('X-CSRF-Token')).toBe('test-csrf-value');
      expect(headers?.get('Content-Type')).toBe('application/json');
      document.cookie = 'pulsai_csrf=; path=/; max-age=0';
    });

    it('forwards AbortSignal when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRefreshResponse),
      });
      const controller = new AbortController();

      await refreshToken('old-refresh-token', controller.signal);

      const init = mockFetch.mock.calls[0]?.[1] as RequestInit | undefined;

      expect(init?.signal).toBe(controller.signal);
    });

    it('single-flights concurrent cookie refreshes (one network call)', async () => {
      let resolveFetch: ((value: unknown) => void) | undefined;

      mockFetch.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFetch = resolve;
          })
      );

      const first = refreshToken();
      const second = refreshToken();

      expect(mockFetch).toHaveBeenCalledTimes(1);

      resolveFetch?.({
        ok: true,
        json: () => Promise.resolve(mockRefreshResponse),
      });

      const [a, b] = await Promise.all([first, second]);

      expect(a.data.access_token).toBe('new-access-token');
      expect(b.data.access_token).toBe('new-access-token');
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  // ===========================================================================
  // Logout Tests
  // ===========================================================================

  describe('logout', () => {
    it('uses cookie-auth transport with credentials include', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await logout('access-token-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/logout'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      );
    });

    it('succeeds with 204 No Content response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await expect(logout('access-token-123')).resolves.toBeUndefined();
    });

    it('throws on non-204 error response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(logout('access-token-123')).rejects.toThrow(AuthError);
    });

    it('forwards AbortSignal when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });
      const controller = new AbortController();

      await logout(undefined, controller.signal);

      const init = mockFetch.mock.calls[0]?.[1] as RequestInit | undefined;

      expect(init?.signal).toBe(controller.signal);
    });
  });

  // ===========================================================================
  // Get Current User Tests
  // ===========================================================================

  describe('getCurrentUser', () => {
    const mockUserResponse = {
      data: {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
        role: 'user',
        subscription_tier: 'free',
        is_active: true,
        is_verified: false,
        locale: 'es',
        created_at: '2026-01-26T00:00:00Z',
      },
      meta: { timestamp: '2026-01-26T00:00:00Z' },
    };

    it('uses cookie-auth transport with credentials include', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

      await getCurrentUser('access-token-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/me'),
        expect.objectContaining({
          credentials: 'include',
        })
      );
    });

    it('returns user data on success', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      });

      const result = await getCurrentUser('access-token-123');

      expect(result.data.id).toBe('user-123');
      expect(result.data.email).toBe('test@example.com');
      expect(result.data.subscription_tier).toBe('free');
    });

    const mockRefreshResponse = {
      data: {
        access_token: 'new-access',
        refresh_token: 'new-refresh',
        token_type: 'bearer',
        expires_in: 1800,
      },
      meta: { timestamp: '2026-01-26T00:00:00Z' },
    };

    it('on 401 calls refresh then retries /me and returns user', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () =>
            Promise.resolve({
              error: { code: 'UNAUTHORIZED', message: 'Invalid token' },
            }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockRefreshResponse),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockUserResponse),
        });

      const result = await getCurrentUser();

      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(mockFetch.mock.calls[0]?.[0]).toContain('/api/v1/auth/me');
      expect(mockFetch.mock.calls[1]?.[0]).toContain('/api/v1/auth/refresh');
      expect(mockFetch.mock.calls[2]?.[0]).toContain('/api/v1/auth/me');
      expect(result.data.id).toBe('user-123');
    });

    it('on 401 when refresh fails, rejects without second /me', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () =>
            Promise.resolve({
              error: { code: 'UNAUTHORIZED', message: 'Unauthorized' },
            }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () =>
            Promise.resolve({
              error: { code: 'INVALID_TOKEN', message: 'Invalid or expired refresh token' },
            }),
        });

      await expect(getCurrentUser()).rejects.toMatchObject({ status: 401 });
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('on 401 after refresh succeeds, second 401 on /me rejects (no refresh loop)', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () =>
            Promise.resolve({
              error: { code: 'UNAUTHORIZED', message: 'Unauthorized' },
            }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(mockRefreshResponse),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () =>
            Promise.resolve({
              error: { code: 'UNAUTHORIZED', message: 'Still unauthorized' },
            }),
        });

      await expect(getCurrentUser()).rejects.toMatchObject({ status: 401 });
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });
  });

  // ===========================================================================
  // Token Storage Tests
  // ===========================================================================

  describe('token storage', () => {
    const mockTokens = {
      accessToken: 'access-123',
      refreshToken: 'refresh-456',
      expiresAt: Math.floor(Date.now() / 1000) + 900,
    };

    describe('saveTokens', () => {
      it('does not persist tokens in web storage (cookie-auth mode)', () => {
        saveTokens(mockTokens);
        expect(localStorage.getItem('pulsai_auth_tokens')).toBeNull();
        expect(sessionStorage.getItem('pulsai_auth_tokens')).toBeNull();
      });
    });

    describe('getStoredTokens', () => {
      it('returns null when no tokens stored in either storage', () => {
        const result = getStoredTokens();

        expect(result).toBeNull();
      });

      it('returns null even if legacy storage has data', () => {
        localStorage.setItem('pulsai_auth_tokens', JSON.stringify(mockTokens));
        expect(getStoredTokens()).toBeNull();
      });
    });

    describe('clearTokens', () => {
      it('removes tokens from both localStorage and sessionStorage', () => {
        localStorage.setItem('pulsai_auth_tokens', JSON.stringify(mockTokens));
        sessionStorage.setItem('pulsai_auth_tokens', JSON.stringify(mockTokens));
        localStorage.setItem('pulsai_auth_storage', 'local');

        clearTokens();

        expect(localStorage.getItem('pulsai_auth_tokens')).toBeNull();
        expect(sessionStorage.getItem('pulsai_auth_tokens')).toBeNull();
        expect(localStorage.getItem('pulsai_auth_storage')).toBeNull();
      });
    });

    describe('isTokenExpired', () => {
      it('returns false for future expiry', () => {
        const futureExpiry = Math.floor(Date.now() / 1000) + 600; // 10 minutes from now

        expect(isTokenExpired(futureExpiry)).toBe(false);
      });

      it('returns true for past expiry', () => {
        const pastExpiry = Math.floor(Date.now() / 1000) - 100; // 100 seconds ago

        expect(isTokenExpired(pastExpiry)).toBe(true);
      });

      it('returns true within 30 second buffer', () => {
        const nearExpiry = Math.floor(Date.now() / 1000) + 20; // 20 seconds from now (within 30s buffer)

        expect(isTokenExpired(nearExpiry)).toBe(true);
      });

      it('returns false just outside 30 second buffer', () => {
        const justOutsideBuffer = Math.floor(Date.now() / 1000) + 35; // 35 seconds from now

        expect(isTokenExpired(justOutsideBuffer)).toBe(false);
      });
    });
  });

  // ===========================================================================
  // handleSessionExpired Tests
  // ===========================================================================

  describe('handleSessionExpired', () => {
    it('clears tokens and dispatches session-expired event', async () => {
      const { handleSessionExpired } = await import('@/services/auth');
      const eventListener = vi.fn();

      // Set up tokens to be cleared
      localStorage.setItem('pulsai_auth_tokens', JSON.stringify({ accessToken: 'test' }));
      window.addEventListener('session-expired', eventListener);

      await handleSessionExpired();

      // Tokens should be cleared
      expect(localStorage.getItem('pulsai_auth_tokens')).toBeNull();
      // Event should be dispatched
      expect(eventListener).toHaveBeenCalledTimes(1);

      window.removeEventListener('session-expired', eventListener);
    });
  });

  // ===========================================================================
  // AuthError Tests
  // ===========================================================================

  describe('getCsrfToken', () => {
    it('returns pulsai_csrf when present', () => {
      vi.spyOn(document, 'cookie', 'get').mockReturnValue('other=1; pulsai_csrf=abc123; x=2');

      expect(getCsrfToken()).toBe('abc123');

      vi.restoreAllMocks();
    });

    it('decodes percent-encoding in the csrf value only', () => {
      vi.spyOn(document, 'cookie', 'get').mockReturnValue('pulsai_csrf=hello%2Bworld');

      expect(getCsrfToken()).toBe('hello+world');

      vi.restoreAllMocks();
    });

    it('does not throw when another cookie would break full-string decodeURIComponent', () => {
      vi.spyOn(document, 'cookie', 'get').mockReturnValue('bad=foo%ZZ; pulsai_csrf=safetoken');

      expect(getCsrfToken()).toBe('safetoken');

      vi.restoreAllMocks();
    });

    it('returns null when pulsai_csrf is absent', () => {
      vi.spyOn(document, 'cookie', 'get').mockReturnValue('other=1');

      expect(getCsrfToken()).toBeNull();

      vi.restoreAllMocks();
    });
  });

  describe('AuthError', () => {
    it('creates error with all properties', () => {
      const error = new AuthError('Test message', 'TEST_CODE', 400, { field: 'email' });

      expect(error.message).toBe('Test message');
      expect(error.code).toBe('TEST_CODE');
      expect(error.status).toBe(400);
      expect(error.details).toEqual({ field: 'email' });
      expect(error.name).toBe('AuthError');
    });

    it('is instanceof Error', () => {
      const error = new AuthError('Test', 'CODE', 400);

      expect(error).toBeInstanceOf(Error);
      expect(error).toBeInstanceOf(AuthError);
    });
  });
});
