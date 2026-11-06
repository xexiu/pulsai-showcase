/**
 * Legal-consent endpoint (Privacy Policy / Terms of Service refresh).
 *
 * Called after admin bumps the required version; the overlay can't dismiss
 * until the user re-accepts.
 */

import { getCsrfToken } from '@/services/auth/csrf';
import { authRequestUrl, handleResponse } from '@/services/auth/internals';
import type { UserResponse } from '@/types/auth';

/** Body shape for ``POST /api/v1/auth/me/legal-accept``. */
export type LegalConsentPayload = {
  terms_consent: boolean;
  data_processing_consent: boolean;
};

/**
 * POST updated legal bundle acceptance.
 *
 * Cookie-auth only — the previous ``(accessToken, payload)`` overload was a
 * legacy artefact; no live caller used it and the runtime ``if (!payload)``
 * guard turned a TS-checkable misuse into a rejected promise that non-async
 * callers could miss. Now strictly typed.
 */
export async function acceptLegalConsent(
  payload: LegalConsentPayload,
  signal?: AbortSignal
): Promise<UserResponse> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken;
  }
  const init: RequestInit = {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(payload),
  };

  if (signal) {
    init.signal = signal;
  }
  const response = await fetch(authRequestUrl('/me/legal-accept'), init);

  return handleResponse<UserResponse>(response);
}
