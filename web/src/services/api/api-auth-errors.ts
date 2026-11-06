/**
 * Auth error keys thrown by authenticatedFetch (no token, session expired, legal gate).
 * UI should translate these via useTranslations('auth')(key).
 */
export const AUTH_ERROR_KEYS = ['sessionExpired', 'legalConsentRequired'] as const;

export type AuthErrorKey = (typeof AUTH_ERROR_KEYS)[number];

export function isAuthErrorKey(message: string): message is AuthErrorKey {
  return (AUTH_ERROR_KEYS as readonly string[]).includes(message);
}
