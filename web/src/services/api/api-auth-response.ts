import { refreshTokenIfNeeded } from '@/services/api/api-token-refresh';
import { fetchWithCredentials } from '@/services/api/api-transport';
import { getCsrfToken, handleSessionExpired } from '@/services/auth';

export async function maybeHandleUnauthorizedResponse(
  response: Response,
  resolvedUrl: string,
  options: RequestInit | undefined,
  headers: Headers
): Promise<Response> {
  if (response.status === 401) {
    // IP_BLOCKED rethrows from refreshSessionAndReschedule (not session-expired).
    const refreshed = await refreshTokenIfNeeded();

    if (!refreshed) {
      void handleSessionExpired();
      throw new Error('sessionExpired');
    }

    // Backend issues a new double-submit token on every refresh; retry must match the new cookie.
    const retryMethod = (options?.method ?? 'GET').toUpperCase();

    if (!['GET', 'HEAD', 'OPTIONS'].includes(retryMethod)) {
      const newCsrf = getCsrfToken();

      if (newCsrf) {
        headers.set('X-CSRF-Token', newCsrf);
      } else {
        headers.delete('X-CSRF-Token');
      }
    }

    const retryResponse = await fetchWithCredentials(resolvedUrl, options, headers);

    if (retryResponse.status === 401) {
      void handleSessionExpired();
      throw new Error('sessionExpired');
    }

    return retryResponse;
  }

  return response;
}

export async function maybeHandleLegalConsentResponse(response: Response): Promise<void> {
  // Legal bundle bump: refresh /me so AuthProvider can show the consent overlay.
  if (response.status === 403) {
    const errJson = (await response
      .clone()
      .json()
      .catch(() => null)) as { error?: { code?: string } } | null;
    const code = errJson?.error?.code;

    if (code === 'LEGAL_CONSENT_REQUIRED') {
      const { dispatchAppEvent } = await import('@/utils/app-events');

      dispatchAppEvent('legal-consent-required');
      throw new Error('legalConsentRequired');
    }
  }
}
