/**
 * CSRF token reader. The backend sets ``pulsai_csrf`` as a readable cookie
 * (NOT HttpOnly) so the client can echo it back as ``X-CSRF-Token`` on
 * state-changing requests. Single SoT for that cookie name + decoding.
 */

const CSRF_COOKIE_PREFIX = 'pulsai_csrf=';

export function getCsrfToken(): string | null {
  if (typeof document === 'undefined') {
    return null;
  }

  for (const segment of document.cookie.split(';')) {
    const part = segment.trim();

    if (!part.startsWith(CSRF_COOKIE_PREFIX)) {
      continue;
    }

    const raw = part.slice(CSRF_COOKIE_PREFIX.length);

    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }

  return null;
}
