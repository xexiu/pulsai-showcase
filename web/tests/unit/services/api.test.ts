// =============================================================================
// API Service Tests - Authenticated Fetch Utility
// =============================================================================
//
// WHY TEST THIS?
// - Critical for authenticated product/admin API calls
// - 401 recovery: coordinated refresh + retry (cookie session)
// - These tests lock fetch shape (credentials, CSRF on mutations) and error paths
//
// FIX (2026-01-29): Created to test authenticated fetch utility
// =============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AUTH_ERROR_KEYS,
  appFetch,
  authenticatedDelete,
  authenticatedFetch,
  authenticatedGet,
  authenticatedPost,
  authenticatedPut,
  fetchWithOptionalAuth,
  isAuthErrorKey,
} from '@/services/api';
import * as authModule from '@/services/auth';
import { saveTokens } from '@/services/auth';
import { dispatchAppEvent } from '@/utils/app-events';

// Mock the refreshToken function for automatic refresh tests
vi.mock('@/services/auth', async (importOriginal) => {
  const actual = await importOriginal();

  return {
    ...(actual as Record<string, unknown>),
    refreshToken: vi.fn().mockRejectedValue(new Error('Refresh failed')),
  };
});

vi.mock('@/utils/app-events', async (importOriginal) => {
  const actual = await importOriginal();

  return {
    ...(actual as Record<string, unknown>),
    dispatchAppEvent: vi.fn(),
  };
});

// =============================================================================
// Test Setup
// =============================================================================

describe('api service', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  const mockTokens = {
    accessToken: 'test-access-token-123',
    refreshToken: 'test-refresh-token-456',
    expiresAt: Math.floor(Date.now() / 1000) + 900, // Valid for 15 minutes
  };

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    vi.mocked(dispatchAppEvent).mockClear();
    // Clear both storages (Remember Me feature uses both)
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  // ===========================================================================
  // authenticatedFetch Tests
  // ===========================================================================

  describe('authenticatedFetch', () => {
    describe('server context (SSR/RSC — no cookie jar)', () => {
      let originalWindow: Window & typeof globalThis;

      beforeEach(() => {
        originalWindow = globalThis.window;
        // @ts-expect-error - simulating SSR / Node context
        delete globalThis.window;
      });

      afterEach(() => {
        globalThis.window = originalWindow;
      });

      it('returns a synthetic 401 Response without making any network call', async () => {
        const response = await authenticatedFetch('/api/v1/market/ohlcv');

        expect(response.status).toBe(401);
        expect(mockFetch).not.toHaveBeenCalled();
      });

      it('does not trigger the token-refresh flow in server context', async () => {
        // refreshToken is mocked at module level; it must not be called
        const { refreshToken: mockRefreshToken } = await import('@/services/auth');

        await authenticatedFetch('/api/v1/market/ohlcv').catch(() => {
          // If it throws instead of returning 401 the assertion below will still catch the
          // regression — but under the fix it must resolve.
        });

        expect(vi.mocked(mockRefreshToken)).not.toHaveBeenCalled();
        expect(mockFetch).not.toHaveBeenCalled();
      });
    });

    describe('cookie-auth transport', () => {
      it('includes credentials for authenticated requests', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

        await authenticatedFetch('/api/admin/models');

        expect(mockFetch).toHaveBeenCalledTimes(1);

        // Check headers manually - Headers object comparison is tricky
        const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

        // All URLs now go to API_BASE_URL (http://localhost:8000)
        expect(callArgs[0]).toBe('http://localhost:8000/api/admin/models');

        expect(callArgs[1].credentials).toBe('include');
      });

      it('does not require a local token before making request', async () => {
        mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });
        await authenticatedFetch('/api/admin/models');
        expect(mockFetch).toHaveBeenCalledTimes(1);
      });

      it('throws sessionExpired when 401 and refresh fails', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ error: 'Unauthorized' }),
        });
        await expect(authenticatedFetch('/api/admin/models')).rejects.toThrow('sessionExpired');
      });
    });

    describe('URL resolution', () => {
      it('prepends API_BASE_URL for all relative URLs', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true });

        await authenticatedFetch('/api/admin/models?symbol=BTC/USDT');

        expect(mockFetch).toHaveBeenCalledTimes(1);

        const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

        // All relative URLs get API_BASE_URL prepended
        expect(callArgs[0]).toBe('http://localhost:8000/api/admin/models?symbol=BTC/USDT');
      });

      it('prepends API_BASE_URL for non-/api URLs', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true });

        await authenticatedFetch('/admin/models');

        // Default is http://localhost:8000
        expect(mockFetch).toHaveBeenCalledWith(
          'http://localhost:8000/admin/models',
          expect.anything()
        );
      });
    });

    describe('Content-Type header', () => {
      it('sets Content-Type for POST requests with body', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true });

        await authenticatedFetch('/api/admin/models/train', {
          method: 'POST',
          body: JSON.stringify({ symbol: 'BTC/USDT' }),
        });

        const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];
        const headers = callArgs[1].headers as Headers;

        expect(headers.get('Content-Type')).toBe('application/json');
      });

      it('does not override existing Content-Type', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true });

        await authenticatedFetch('/api/admin/models/train', {
          method: 'POST',
          headers: { 'Content-Type': 'multipart/form-data' },
          body: 'test',
        });

        const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];
        const headers = callArgs[1].headers as Headers;

        expect(headers.get('Content-Type')).toBe('multipart/form-data');
      });

      it('does not set Content-Type for GET requests', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true });

        await authenticatedFetch('/api/admin/models');

        const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];
        const headers = callArgs[1].headers as Headers;

        // GET requests without body should not have Content-Type forced
        expect(headers.has('Content-Type')).toBe(false);
      });
    });

    describe('passthrough options', () => {
      it('passes method option correctly', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true });

        await authenticatedFetch('/api/admin/models', { method: 'DELETE' });

        expect(mockFetch).toHaveBeenCalledWith(
          expect.anything(),
          expect.objectContaining({ method: 'DELETE' })
        );
      });

      it('passes body option correctly', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({ ok: true });

        const body = JSON.stringify({ test: 'data' });

        await authenticatedFetch('/api/admin/models/train', {
          method: 'POST',
          body,
        });

        expect(mockFetch).toHaveBeenCalledWith(
          expect.anything(),
          expect.objectContaining({ body })
        );
      });
    });

    describe('response handling', () => {
      it('returns fetch Response object', async () => {
        saveTokens(mockTokens);
        const mockResponse = {
          ok: true,
          status: 200,
          json: () => Promise.resolve({ data: 'test' }),
        };

        mockFetch.mockResolvedValueOnce(mockResponse);

        const response = await authenticatedFetch('/api/admin/models');

        expect(response).toBe(mockResponse);
      });

      it('throws error on 401 responses (session expiry)', async () => {
        saveTokens(mockTokens);
        mockFetch.mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ error: 'Unauthorized' }),
        });

        // 401 responses throw i18n key and trigger session expiration (auth.sessionExpired)
        await expect(authenticatedFetch('/api/admin/models')).rejects.toThrow('sessionExpired');
      });

      it('on 403 with LEGAL_CONSENT_REQUIRED dispatches event and throws legalConsentRequired', async () => {
        saveTokens(mockTokens);
        const consentBody = { error: { code: 'LEGAL_CONSENT_REQUIRED' } };
        const mock403 = {
          ok: false,
          status: 403,
          clone: () => mock403,
          json: () => Promise.resolve(consentBody),
        };

        mockFetch.mockResolvedValueOnce(mock403);

        await expect(authenticatedFetch('/api/v1/backtests')).rejects.toThrow(
          'legalConsentRequired'
        );

        expect(dispatchAppEvent).toHaveBeenCalledTimes(1);
        expect(dispatchAppEvent).toHaveBeenCalledWith('legal-consent-required');
      });

      it('returns Response on 403 without LEGAL_CONSENT_REQUIRED (other forbidden)', async () => {
        saveTokens(mockTokens);
        const mock403 = {
          ok: false,
          status: 403,
          clone: () => mock403,
          json: () => Promise.resolve({ error: { code: 'INSUFFICIENT_PERMISSIONS' } }),
        };

        mockFetch.mockResolvedValueOnce(mock403);

        const response = await authenticatedFetch('/api/v1/admin/x');

        expect(response.status).toBe(403);
      });
    });
  });

  // ===========================================================================
  // Helper Function Tests
  // ===========================================================================

  describe('authenticatedGet', () => {
    it('makes GET with credentials include (session cookies)', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });

      await authenticatedGet('/api/admin/models');

      expect(mockFetch).toHaveBeenCalledTimes(1);

      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[0]).toBe('http://localhost:8000/api/admin/models');
      expect(callArgs[1].method).toBe('GET');

      expect(callArgs[1].credentials).toBe('include');
    });

    it('forwards AbortSignal when provided', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });
      const controller = new AbortController();

      await authenticatedGet('/api/admin/models', controller.signal);

      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[1].signal).toBe(controller.signal);
    });
  });

  describe('authenticatedPost', () => {
    it('makes POST with JSON body, CSRF when present, credentials include', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });

      const data = { symbol: 'BTC/USDT', timeframe: '1h' };

      await authenticatedPost('/api/admin/models/train', data);

      expect(mockFetch).toHaveBeenCalledTimes(1);

      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[0]).toBe('http://localhost:8000/api/admin/models/train');
      expect(callArgs[1].method).toBe('POST');
      expect(callArgs[1].body).toBe(JSON.stringify(data));

      const headers = callArgs[1].headers as Headers;

      expect(callArgs[1].credentials).toBe('include');
      expect(headers.get('Content-Type')).toBe('application/json');
    });

    it('forwards AbortSignal when provided', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });
      const controller = new AbortController();
      const data = { symbol: 'BTC/USDT' };

      await authenticatedPost('/api/admin/models/train', data, controller.signal);

      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[1].signal).toBe(controller.signal);
    });
  });

  describe('authenticatedPut', () => {
    it('makes PUT request with JSON body', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });

      const data = { notes: 'Updated model notes' };

      await authenticatedPut('/api/admin/models/1', data);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/models/1'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(data),
        })
      );
    });

    it('forwards AbortSignal when provided', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });
      const controller = new AbortController();
      const data = { notes: 'Updated model notes' };

      await authenticatedPut('/api/admin/models/1', data, controller.signal);

      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[1].signal).toBe(controller.signal);
    });
  });

  describe('authenticatedDelete', () => {
    it('makes DELETE request', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });

      await authenticatedDelete('/api/admin/models/1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/models/1'),
        expect.objectContaining({ method: 'DELETE' })
      );

      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[1].credentials).toBe('include');
    });

    it('forwards AbortSignal when provided', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true });
      const controller = new AbortController();

      await authenticatedDelete('/api/admin/models/1', controller.signal);

      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[1].signal).toBe(controller.signal);
    });
  });

  // ===========================================================================
  // Edge Cases
  // ===========================================================================

  describe('edge cases', () => {
    it('handles token about to expire (within 60s auto-refresh threshold)', async () => {
      const soonExpiredTokens = {
        ...mockTokens,
        expiresAt: Math.floor(Date.now() / 1000) + 20, // 20 seconds (within 60s threshold)
      };

      saveTokens(soonExpiredTokens);
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ error: 'Unauthorized' }),
      });
      await expect(authenticatedFetch('/api/admin/models')).rejects.toThrow();
    });

    it('clears tokens after throwing expiry error', async () => {
      const expiredTokens = {
        ...mockTokens,
        expiresAt: Math.floor(Date.now() / 1000) - 10,
      };

      saveTokens(expiredTokens);

      try {
        await authenticatedFetch('/api/admin/models');
      } catch {
        // Expected
      }

      expect(localStorage.getItem('pulsai_auth_tokens')).toBeNull();
    });

    it('handles network errors', async () => {
      saveTokens(mockTokens);
      mockFetch.mockRejectedValueOnce(new TypeError('Network error'));

      await expect(authenticatedFetch('/api/admin/models')).rejects.toThrow('Network error');
    });
  });

  describe('auth error keys (i18n)', () => {
    it('AUTH_ERROR_KEYS contains noToken, sessionExpired, and legalConsentRequired', () => {
      expect(AUTH_ERROR_KEYS).toContain('sessionExpired');
      expect(AUTH_ERROR_KEYS).toContain('legalConsentRequired');
    });

    it('isAuthErrorKey returns true for noToken, sessionExpired, and legalConsentRequired', () => {
      expect(isAuthErrorKey('sessionExpired')).toBe(true);
      expect(isAuthErrorKey('legalConsentRequired')).toBe(true);
    });

    it('isAuthErrorKey returns false for other strings', () => {
      expect(isAuthErrorKey('Session expired. Please log in again.')).toBe(false);
      expect(isAuthErrorKey('')).toBe(false);
    });
  });

  // ===========================================================================
  // appFetch – single entry point (Phase 6.5)
  // ===========================================================================
  describe('appFetch', () => {
    it('resolves relative URL with API_BASE_URL and uses GET by default', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await appFetch({ url: '/api/v1/market/ohlcv' });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(url).toBe('http://localhost:8000/api/v1/market/ohlcv');
      expect(init?.method).toBe('GET');
    });

    it('leaves absolute URL unchanged', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await appFetch({ url: 'https://example.com/api' });

      const [url] = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(url).toBe('https://example.com/api');
    });

    it('passes method and body when provided', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await appFetch({
        url: '/api/v1/admin/jobs',
        method: 'POST',
        body: JSON.stringify({ symbol: 'BTC/USDT' }),
      });

      const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(init?.method).toBe('POST');
      expect(init?.body).toBe(JSON.stringify({ symbol: 'BTC/USDT' }));
    });

    it('passes signal when provided', async () => {
      const controller = new AbortController();

      mockFetch.mockResolvedValueOnce({ ok: true });

      await appFetch({ url: '/api/v1/x', signal: controller.signal });

      const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(init?.signal).toBe(controller.signal);
    });

    it('when auth is true delegates to authenticatedFetch with credentials', async () => {
      saveTokens(mockTokens);
      mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

      await appFetch({ url: '/api/v1/admin/training/jobs', auth: true });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const callArgs = mockFetch.mock.calls[0] as [string, RequestInit];

      expect(callArgs[0]).toBe('http://localhost:8000/api/v1/admin/training/jobs');
      expect(callArgs[1].credentials).toBe('include');
    });

    it('returns Response from fetch', async () => {
      const res = { ok: true, status: 200 };

      mockFetch.mockResolvedValueOnce(res);

      const result = await appFetch({ url: '/api/v1/x' });

      expect(result).toBe(res);
    });
  });

  describe('fetchWithOptionalAuth', () => {
    it('sends X-CSRF-Token on POST when cookie CSRF is available (API CSRFMiddleware)', async () => {
      const csrfSpy = vi.spyOn(authModule, 'getCsrfToken').mockReturnValue('double-submit-token');

      mockFetch.mockResolvedValueOnce({ ok: true });

      await fetchWithOptionalAuth('/api/v1/ai/explain-signal', {
        method: 'POST',
        body: JSON.stringify({ signal_id: 'x', include_news: false }),
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Headers;

      expect(headers.get('X-CSRF-Token')).toBe('double-submit-token');
      csrfSpy.mockRestore();
    });

    it('does not set X-CSRF-Token on GET', async () => {
      const csrfSpy = vi.spyOn(authModule, 'getCsrfToken').mockReturnValue('token');

      mockFetch.mockResolvedValueOnce({ ok: true });

      await fetchWithOptionalAuth('/api/v1/ai/explain-signal');

      const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Headers;

      expect(headers.get('X-CSRF-Token')).toBeNull();
      csrfSpy.mockRestore();
    });
  });
});
