import { resolveFetchUrl } from '@/config/api';
import {
  maybeHandleLegalConsentResponse,
  maybeHandleUnauthorizedResponse,
} from '@/services/api/api-auth-response';
import { fetchWithCredentials } from '@/services/api/api-transport';
import { getCsrfToken } from '@/services/auth';
import { HTTP_STATUS } from '@/utils/constants';

/**
 * Authenticated fetch for cookie-backed sessions (and optional Bearer if callers add it).
 *
 * Features:
 * - Sends `credentials: 'include'` so HttpOnly access/refresh cookies reach the API (and Next `/api` proxy)
 * - On 401, runs a single shared `POST /auth/refresh`, then retries the original request once
 * - If refresh fails, dispatches session-expired handling (see handleSessionExpired)
 *
 * WHY: Access tokens are not read from Web Storage in cookie-auth mode; reactive refresh keeps sessions alive.
 *
 * WHY the server-context guard?
 * Cookie auth (`credentials: 'include'`) requires a browser cookie jar. In a Node/server context
 * (SSR, RSC, or test) there is no cookie jar, so every request to a protected endpoint 401s
 * immediately, and the reactive refresh also 401s — spamming the backend with guaranteed-doomed
 * unauthenticated round-trips. Short-circuiting with a synthetic 401 Response is
 * behavior-equivalent for callers (which already handle 401 for authed endpoints) while
 * eliminating the useless network traffic.
 *
 * USAGE:
 * ```typescript
 * const response = await authenticatedFetch('/api/v1/admin/models');
 * const data = await response.json();
 * ```
 *
 * @param url - Relative `/api/v1/...` or absolute URL (see {@link resolveFetchUrl})
 * @param options - Standard fetch RequestInit options
 * @returns Promise<Response> - Standard fetch Response
 * @throws Error if no valid token is available or refresh fails
 */
export async function authenticatedFetch(url: string, options?: RequestInit): Promise<Response> {
  // Cookie auth requires the browser cookie jar. In a Node/server context (SSR, RSC) there is no
  // cookie jar, so `credentials: 'include'` attaches nothing and every protected endpoint 401s.
  // Return a synthetic 401 immediately to avoid spamming the backend with doomed unauthenticated
  // requests and to prevent the reactive refresh flow (which would also 401 for the same reason).
  if (typeof window === 'undefined') {
    return new Response(null, { status: HTTP_STATUS.UNAUTHORIZED });
  }

  const headers = new Headers(options?.headers);
  const method = (options?.method ?? 'GET').toUpperCase();
  const csrfToken = getCsrfToken();

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken);
  }

  // Only set Content-Type for non-GET requests or if body is present
  if (options?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const resolvedUrl = resolveFetchUrl(url);

  const response = await fetchWithCredentials(resolvedUrl, options, headers);

  const responseAfterAuth = await maybeHandleUnauthorizedResponse(
    response,
    resolvedUrl,
    options,
    headers
  );

  await maybeHandleLegalConsentResponse(responseAfterAuth);

  return responseAfterAuth;
}
