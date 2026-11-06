/**
 * Internal helpers shared by the auth service surface.
 *
 * Single SoT for: URL resolution under ``/api/v1/auth``, the typed error
 * thrown for non-2xx responses, the response parser, and the small
 * cross-module types. Kept private to ``@/services/auth/*`` — callers
 * outside this folder import from ``@/services/auth`` (the barrel).
 */

import { resolveFetchUrl } from '@/config/api';
import type { ErrorResponse } from '@/types/auth';

export type MessageResponse = {
  data: { message: string };
  meta: { timestamp: string };
};

export type StoredTokens = {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
};

/**
 * Auth API path under ``/api/v1/auth``. Uses {@link resolveFetchUrl} so
 * browser calls hit the Next proxy (``/api/auth/...`` → backend) and avoid
 * CORS.
 */
export function authRequestUrl(path: string): string {
  const suffix = path.startsWith('/') ? path : `/${path}`;

  return resolveFetchUrl(`/api/v1/auth${suffix}`);
}

export class AuthError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'AuthError';
  }
}

export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = (await response.json().catch(() => null)) as ErrorResponse | null;

    throw new AuthError(
      errorData?.error?.message || 'An error occurred',
      errorData?.error?.code || 'UNKNOWN_ERROR',
      response.status,
      errorData?.error?.details
    );
  }

  return response.json() as Promise<T>;
}
