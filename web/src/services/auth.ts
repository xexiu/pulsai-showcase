/**
 * Auth service — public surface.
 *
 * The implementation is split across cohesive SRP-scoped modules under
 * ``@/services/auth/*``:
 *
 *   - ``internals``      — typed error, response parser, URL builder, types
 *   - ``csrf``           — ``getCsrfToken`` cookie reader (SoT for the
 *                          ``pulsai_csrf`` cookie name)
 *   - ``credentials``    — ``register`` / ``login`` / ``refreshToken``
 *   - ``session``        — ``logout`` / ``getCurrentUser`` /
 *                          ``handleSessionExpired`` / ``isTokenExpired``
 *   - ``legal-consent``  — ``acceptLegalConsent`` + payload type
 *   - ``password``       — ``forgotPassword`` / ``resetPassword``
 *   - ``token-storage``  — ``clearTokens`` / ``saveTokens`` /
 *                          ``getStoredTokens`` (cookie-auth no-op shims +
 *                          legacy-storage hygiene)
 *
 * Callers continue to import from ``@/services/auth`` — this barrel
 * preserves the public surface unchanged.
 */

export { acceptLegalConsent, type LegalConsentPayload } from '@/services/auth/legal-consent';
export { login, refreshToken, register } from '@/services/auth/credentials';
export { getCsrfToken } from '@/services/auth/csrf';
export { AuthError, type StoredTokens } from '@/services/auth/internals';
export { forgotPassword, resetPassword } from '@/services/auth/password';
export {
  getCurrentUser,
  handleSessionExpired,
  isTokenExpired,
  logout,
} from '@/services/auth/session';
export { clearTokens, getStoredTokens, saveTokens } from '@/services/auth/token-storage';
