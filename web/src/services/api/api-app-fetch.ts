import { resolveFetchUrl } from '@/config/api';
import { authenticatedFetch } from '@/services/api/api-authenticated-fetch';
import type { AppFetchOptions } from '@/services/api/api-types';
import { getCsrfToken } from '@/services/auth';
import { fetchWithRetry } from '@/utils/retry';

/**
 * Single fetch entry point for app API calls.
 *
 * WHY?
 * - One place for auth, retry, timeout, and AbortSignal (Amphora-style).
 * - Fetchers in queryFetchers.ts call this instead of authenticatedFetch/fetchWithRetry directly.
 *
 * Behavior:
 * - auth true → authenticatedFetch (credentials include cookies, CSRF on mutating methods, 401 → refresh → retry).
 * - retry true (and not auth) → fetchWithRetry (timeout, retries, abort).
 * - auth wins if both set; auth+retry not yet supported.
 *
 * @returns Promise<Response> – caller parses JSON and handles !response.ok.
 */
export async function appFetch(options: AppFetchOptions): Promise<Response> {
  const {
    url,
    method = 'GET',
    signal,
    auth = false,
    retry = false,
    timeoutMs,
    maxRetries,
    body,
    headers,
  } = options;

  const resolvedUrl = resolveFetchUrl(url);
  const init: RequestInit = { method };

  if (signal !== undefined) init.signal = signal;
  if (body !== undefined) init.body = body;
  if (headers !== undefined) init.headers = headers;

  if (auth) {
    // authenticatedFetch applies resolveFetchUrl — pass canonical `/api/v1/...` path.
    return authenticatedFetch(url, init);
  }

  if (retry) {
    const retryOpts: { timeoutMs?: number; maxRetries?: number } = {};

    if (timeoutMs !== undefined) retryOpts.timeoutMs = timeoutMs;
    if (maxRetries !== undefined) retryOpts.maxRetries = maxRetries;

    return fetchWithRetry(resolvedUrl, init, retryOpts);
  }

  return fetch(resolvedUrl, init);
}

/**
 * POST/GET with JSON body when the route accepts anonymous users but applies
 * tier upgrades when Authorization is present (e.g. POST /api/v1/ai/explain-signal).
 *
 * Same URL resolution as appFetch; does not throw on missing token (unlike auth: true).
 */
export async function fetchWithOptionalAuth(
  url: string,
  init: RequestInit = {}
): Promise<Response> {
  const resolvedUrl = resolveFetchUrl(url);
  const headers = new Headers(init.headers);
  const method = (init.method ?? 'GET').toUpperCase();
  const csrfToken = getCsrfToken();

  // Cookie-auth mutating requests must send CSRF (SoT: CSRFMiddleware on API).
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken);
  }

  if (init.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return fetch(resolvedUrl, { ...init, headers, credentials: 'include' });
}
