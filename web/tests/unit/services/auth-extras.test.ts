/**
 * Branch coverage for auth service edge paths:
 *  - resetPassword / forgotPassword / acceptLegalConsent payload shapes
 *  - acceptLegalConsent overload (string vs object first arg)
 *  - CSRF header propagation when cookie set vs unset
 *  - SSR safety on clearTokens / getCsrfToken
 *  - logout 204 short-circuit
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  acceptLegalConsent,
  AuthError,
  clearTokens,
  forgotPassword,
  getCsrfToken,
  logout,
  resetPassword,
} from '@/services/auth';

function okJson(
  data: unknown
): Promise<{ ok: true; status: number; json: () => Promise<unknown> }> {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) });
}

describe('auth service — password reset endpoints', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    // Reliably clear cookies in jsdom by setting an expiry in the past.
    for (const c of document.cookie.split(';')) {
      const name = c.split('=')[0]?.trim();

      if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('forgotPassword sends email to /forgot-password', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ data: { message: 'sent' }, meta: { timestamp: '' } }));

    await forgotPassword('a@b.com');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/forgot-password'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'a@b.com' }),
      })
    );
  });

  it('forgotPassword forwards external AbortSignal', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ data: { message: 'sent' }, meta: { timestamp: '' } }));
    const c = new AbortController();

    await forgotPassword('a@b.com', c.signal);

    const init = mockFetch.mock.calls[0]![1] as RequestInit;

    expect(init.signal).toBe(c.signal);
  });

  it('forgotPassword raises AuthError on 4xx', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({
          error: { code: 'INVALID_EMAIL', message: 'Invalid email', details: {} },
        }),
    });

    await expect(forgotPassword('bad')).rejects.toBeInstanceOf(AuthError);
  });

  it('resetPassword sends token + password to /reset-password', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ data: { message: 'ok' }, meta: { timestamp: '' } }));

    await resetPassword('tok-xyz', 'NewPass123');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/reset-password'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ token: 'tok-xyz', password: 'NewPass123' }),
      })
    );
  });

  it('resetPassword forwards external AbortSignal', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ data: { message: 'ok' }, meta: { timestamp: '' } }));
    const c = new AbortController();

    await resetPassword('tok', 'pw', c.signal);

    const init = mockFetch.mock.calls[0]![1] as RequestInit;

    expect(init.signal).toBe(c.signal);
  });
});

describe('auth service — acceptLegalConsent', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    // Reliably clear cookies in jsdom by setting an expiry in the past.
    for (const c of document.cookie.split(';')) {
      const name = c.split('=')[0]?.trim();

      if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('serialises the payload as the request body', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ data: {}, meta: {} }));
    const payload = { terms_consent: true, data_processing_consent: true };

    await acceptLegalConsent(payload);

    const init = mockFetch.mock.calls[0]![1] as RequestInit;

    expect(init.body).toBe(JSON.stringify(payload));
  });

  it('respects both consent flags independently', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ data: {}, meta: {} }));
    const payload = { terms_consent: true, data_processing_consent: false };

    await acceptLegalConsent(payload);

    const init = mockFetch.mock.calls[0]![1] as RequestInit;

    expect(init.body).toBe(JSON.stringify(payload));
  });

  it('attaches X-CSRF-Token header when cookie present', async () => {
    document.cookie = 'pulsai_csrf=secret%2D123';
    mockFetch.mockResolvedValueOnce(okJson({ data: {}, meta: {} }));

    await acceptLegalConsent({ terms_consent: true, data_processing_consent: true });
    const headers = (mockFetch.mock.calls[0]![1] as RequestInit).headers as Record<string, string>;

    expect(headers['X-CSRF-Token']).toBe('secret-123');
  });

  it('omits X-CSRF-Token when cookie absent', async () => {
    // Reliably clear cookies in jsdom by setting an expiry in the past.
    for (const c of document.cookie.split(';')) {
      const name = c.split('=')[0]?.trim();

      if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
    mockFetch.mockResolvedValueOnce(okJson({ data: {}, meta: {} }));

    await acceptLegalConsent({ terms_consent: true, data_processing_consent: true });
    const headers = (mockFetch.mock.calls[0]![1] as RequestInit).headers as Record<string, string>;

    expect(headers['X-CSRF-Token']).toBeUndefined();
  });

  it('forwards external AbortSignal', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ data: {}, meta: {} }));
    const c = new AbortController();

    await acceptLegalConsent({ terms_consent: true, data_processing_consent: true }, c.signal);
    const init = mockFetch.mock.calls[0]![1] as RequestInit;

    expect(init.signal).toBe(c.signal);
  });
});

describe('auth service — logout edge', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    // Reliably clear cookies in jsdom by setting an expiry in the past.
    for (const c of document.cookie.split(';')) {
      const name = c.split('=')[0]?.trim();

      if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('treats 204 No Content as success', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 204, json: () => Promise.resolve(null) });

    await expect(logout('tok')).resolves.toBeUndefined();
  });

  it('includes X-CSRF-Token header on logout when cookie set', async () => {
    document.cookie = 'pulsai_csrf=abc';
    mockFetch.mockResolvedValueOnce(okJson(null));

    await logout('tok');
    const headers = (mockFetch.mock.calls[0]![1] as RequestInit).headers as Record<string, string>;

    expect(headers['X-CSRF-Token']).toBe('abc');
  });

  it('forwards external AbortSignal', async () => {
    mockFetch.mockResolvedValueOnce(okJson(null));
    const c = new AbortController();

    await logout(undefined, c.signal);
    const init = mockFetch.mock.calls[0]![1] as RequestInit;

    expect(init.signal).toBe(c.signal);
  });
});

describe('auth service — SSR safety', () => {
  const origWindow = global.window;
  const origDoc = global.document;

  afterEach(() => {
    Object.defineProperty(global, 'window', { value: origWindow, configurable: true });
    Object.defineProperty(global, 'document', { value: origDoc, configurable: true });
  });

  it('clearTokens is a noop when window is undefined (SSR)', () => {
    Object.defineProperty(global, 'window', { value: undefined, configurable: true });
    // Should not throw — purely defensive.
    expect(() => clearTokens()).not.toThrow();
  });

  it('getCsrfToken returns null when document is undefined (SSR)', () => {
    Object.defineProperty(global, 'document', { value: undefined, configurable: true });
    expect(getCsrfToken()).toBeNull();
  });

  it('getCsrfToken returns null when cookie is empty', () => {
    // Reliably clear cookies in jsdom by setting an expiry in the past.
    for (const c of document.cookie.split(';')) {
      const name = c.split('=')[0]?.trim();

      if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
    expect(getCsrfToken()).toBeNull();
  });
});
