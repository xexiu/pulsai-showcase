// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';

describe('resolveFetchUrl', () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it('in Vitest maps relative /api/v1 paths to API_BASE_URL', async () => {
    const { resolveFetchUrl, API_BASE_URL } = await import('@/config/api');

    expect(resolveFetchUrl('/api/v1/signals/latest')).toBe(`${API_BASE_URL}/api/v1/signals/latest`);
  });

  it('builds frontend release with short build SHA when provided', async () => {
    const prevVersion = process.env['NEXT_PUBLIC_APP_VERSION'];
    const prevSha = process.env['NEXT_PUBLIC_BUILD_SHA'];

    try {
      process.env['NEXT_PUBLIC_APP_VERSION'] = '1.2.3';
      process.env['NEXT_PUBLIC_BUILD_SHA'] = 'abcdef1234567890';
      vi.resetModules();
      const { FRONTEND_RELEASE } = await import('@/config/api');

      expect(FRONTEND_RELEASE).toBe('1.2.3+abcdef12');
    } finally {
      process.env['NEXT_PUBLIC_APP_VERSION'] = prevVersion;
      process.env['NEXT_PUBLIC_BUILD_SHA'] = prevSha;
    }
  });

  it('normalizes absolute same-origin /api/v1 URLs to the same result as relative (Vitest)', async () => {
    const { resolveFetchUrl, API_BASE_URL } = await import('@/config/api');

    const relative = resolveFetchUrl('/api/v1/exchanges/supported');
    const absolute = resolveFetchUrl(`${API_BASE_URL}/api/v1/exchanges/supported`);

    expect(relative).toBe(absolute);
    expect(relative).toBe(`${API_BASE_URL}/api/v1/exchanges/supported`);
  });

  it('leaves unrelated absolute URLs unchanged', async () => {
    const { resolveFetchUrl } = await import('@/config/api');

    expect(resolveFetchUrl('https://cdn.example.com/asset.js')).toBe(
      'https://cdn.example.com/asset.js'
    );
  });

  it('in browser (no VITEST), localhost API base resolves to direct backend URL', async () => {
    const prevVitest = process.env['VITEST'];

    try {
      delete process.env['VITEST'];
      vi.stubGlobal('window', {});

      const { resolveFetchUrl, API_BASE_URL } = await import('@/config/api');

      expect(resolveFetchUrl(`${API_BASE_URL}/api/v1/exchanges`)).toBe(
        `${API_BASE_URL}/api/v1/exchanges`
      );
    } finally {
      process.env['VITEST'] = prevVitest ?? 'true';
    }
  });
});

describe('resolveEventStreamUrl', () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it('in Vitest maps stream path to API_BASE_URL like resolveFetchUrl', async () => {
    const { resolveEventStreamUrl, API_BASE_URL } = await import('@/config/api');

    expect(resolveEventStreamUrl('/api/v1/ai/explain-signal-stream?x=1')).toBe(
      `${API_BASE_URL}/api/v1/ai/explain-signal-stream?x=1`
    );
  });

  it('in browser keeps same-origin /api/v1 path for cookie auth (local + prod)', async () => {
    const prevVitest = process.env['VITEST'];

    try {
      delete process.env['VITEST'];
      vi.stubGlobal('window', {});

      const { resolveEventStreamUrl, API_BASE_URL } = await import('@/config/api');

      expect(
        resolveEventStreamUrl('/api/v1/ai/explain-signal-stream?signal_id=abc&language=es')
      ).toBe('/api/v1/ai/explain-signal-stream?signal_id=abc&language=es');
      expect(
        resolveEventStreamUrl(`${API_BASE_URL}/api/v1/ai/explain-signal-stream?language=es`)
      ).toBe('/api/v1/ai/explain-signal-stream?language=es');
    } finally {
      process.env['VITEST'] = prevVitest ?? 'true';
    }
  });
});
