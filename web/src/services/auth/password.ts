/**
 * Password recovery endpoints (Sprint 1.6b).
 *
 * ``forgotPassword`` is intentionally noisy-success: always 200 to avoid
 * user enumeration. ``resetPassword`` consumes a one-shot email token.
 */

import { authRequestUrl, handleResponse, type MessageResponse } from '@/services/auth/internals';

/**
 * Request password reset email.
 *
 * SECURITY: Always returns success (no user enumeration).
 */
export async function forgotPassword(
  email: string,
  signal?: AbortSignal
): Promise<MessageResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email }),
  };

  if (signal) {
    init.signal = signal;
  }
  const response = await fetch(authRequestUrl('/forgot-password'), init);

  return handleResponse<MessageResponse>(response);
}

/**
 * Reset password with token from email.
 */
export async function resetPassword(
  token: string,
  password: string,
  signal?: AbortSignal
): Promise<MessageResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ token, password }),
  };

  if (signal) {
    init.signal = signal;
  }
  const response = await fetch(authRequestUrl('/reset-password'), init);

  return handleResponse<MessageResponse>(response);
}
