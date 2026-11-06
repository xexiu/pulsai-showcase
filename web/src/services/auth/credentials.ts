/**
 * Credential-issuing auth endpoints: register, login, refresh.
 *
 * These run BEFORE the user is authenticated, so they use raw ``fetch`` —
 * the shared authenticated transport (``appFetch``) requires tokens.
 */

import { getCsrfToken } from '@/services/auth/csrf';
import { authRequestUrl, handleResponse } from '@/services/auth/internals';
import type {
  LoginCredentials,
  RefreshTokenData,
  RegisterData,
  RegisterResponse,
  TokenResponse,
} from '@/types/auth';

/**
 * Single-flight in-progress cookie refresh.
 *
 * WHY: Refresh tokens are single-use (jti blacklisted on rotate). Concurrent
 * ``/auth/refresh`` from ``getCurrentUser`` + ``authenticatedFetch`` + proactive
 * timer races → one wins, one gets INVALID_TOKEN → false "session expired" /
 * login flash while HttpOnly cookies from the winner remain valid (Cmd+R twice).
 */
let inFlightRefresh: Promise<TokenResponse> | null = null;

/**
 * Register a new user.
 */
export async function register(
  data: RegisterData,
  signal?: AbortSignal
): Promise<RegisterResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  };

  if (signal) {
    init.signal = signal;
  }
  const response = await fetch(authRequestUrl('/register'), init);

  return handleResponse<RegisterResponse>(response);
}

/**
 * Login with email and password.
 */
export async function login(
  credentials: LoginCredentials,
  signal?: AbortSignal
): Promise<TokenResponse> {
  const { email, password, remember_me = true } = credentials;
  const init: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password, remember_me }),
  };

  if (signal) {
    init.signal = signal;
  }
  const response = await fetch(authRequestUrl('/login'), init);

  return handleResponse<TokenResponse>(response);
}

async function performRefreshRequest(
  refreshTokenValue?: string,
  signal?: AbortSignal
): Promise<TokenResponse> {
  const headers = new Headers({ 'Content-Type': 'application/json' });
  const csrfToken = getCsrfToken();

  if (csrfToken) {
    headers.set('X-CSRF-Token', csrfToken);
  }

  const body: RefreshTokenData | undefined = refreshTokenValue
    ? { refresh_token: refreshTokenValue }
    : undefined;
  const init: RequestInit = {
    method: 'POST',
    headers,
    credentials: 'include',
  };

  if (signal) {
    init.signal = signal;
  }

  if (body) {
    init.body = JSON.stringify(body);
  }
  const response = await fetch(authRequestUrl('/refresh'), init);

  return handleResponse<TokenResponse>(response);
}

/**
 * Refresh access token using refresh token.
 *
 * Concurrent callers share one in-flight request (see ``inFlightRefresh``).
 */
export async function refreshToken(
  refreshTokenValue?: string,
  signal?: AbortSignal
): Promise<TokenResponse> {
  if (!inFlightRefresh) {
    inFlightRefresh = performRefreshRequest(refreshTokenValue, signal).finally(() => {
      inFlightRefresh = null;
    });
  }

  return inFlightRefresh;
}
