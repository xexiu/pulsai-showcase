// @vitest-environment node
/**
 * Behaviour tests for api-transport (proxy 5xx fallback + direct API URL).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fetchWithCredentials,
  shouldFallbackToDirectApi,
  toDirectApiUrl,
} from '@/services/api/api-transport';

vi.mock('@/config/api', () => ({
  API_BASE_URL: 'http://test-api.local:8000',
  resolveFetchUrl: (url: string) => url,
}));

describe('api-transport', () => {
  const originalFetch = global.fetch;
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockReset();
    global.fetch = mockFetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  describe('shouldFallbackToDirectApi', () => {
    it('returns false for non-proxy paths', () => {
      expect(shouldFallbackToDirectApi('http://test-api.local:8000/api/v1/foo', 503)).toBe(false);
    });

    it('returns false for proxy 4xx', () => {
      expect(shouldFallbackToDirectApi('/api/v1/market/ohlcv', 404)).toBe(false);
    });

    it('returns true for proxy 5xx', () => {
      expect(shouldFallbackToDirectApi('/api/v1/market/ohlcv', 502)).toBe(true);
    });
  });

  describe('toDirectApiUrl', () => {
    it('prepends API_BASE_URL for relative paths', () => {
      expect(toDirectApiUrl('/api/v1/health')).toBe('http://test-api.local:8000/api/v1/health');
    });

    it('returns absolute URLs unchanged', () => {
      const absolute = 'https://cdn.example.com/asset.js';

      expect(toDirectApiUrl(absolute)).toBe(absolute);
    });
  });

  describe('fetchWithCredentials', () => {
    it('retries direct API when proxy returns 5xx', async () => {
      const headers = new Headers({ Accept: 'application/json' });
      const proxyResponse = new Response(null, { status: 502 });
      const directResponse = new Response(JSON.stringify({ ok: true }), { status: 200 });

      mockFetch.mockResolvedValueOnce(proxyResponse).mockResolvedValueOnce(directResponse);

      const result = await fetchWithCredentials('/api/v1/market/ohlcv', { method: 'GET' }, headers);

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(mockFetch.mock.calls[0]?.[0]).toBe('/api/v1/market/ohlcv');
      expect(mockFetch.mock.calls[1]?.[0]).toBe('http://test-api.local:8000/api/v1/market/ohlcv');
      expect(result.status).toBe(200);
    });

    it('does not retry when proxy returns 2xx', async () => {
      const headers = new Headers();
      const okResponse = new Response('{}', { status: 200 });

      mockFetch.mockResolvedValueOnce(okResponse);

      const result = await fetchWithCredentials('/api/v1/user/me', undefined, headers);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(result).toBe(okResponse);
    });
  });
});
