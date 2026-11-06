/**
 * API Configuration - Single Source of Truth
 *
 * WHY THIS FILE?
 * - DRY: API_BASE_URL was duplicated in 7+ files
 * - Single source of truth for API configuration
 * - Easy to change environment-specific values
 *
 * USAGE:
 * ```typescript
 * import { API_BASE_URL, SITE_URL, getWsUrl } from '@/config/api';
 * ```
 *
 * @see docs/04-structural/CODING_STANDARDS.md for DRY principles
 */

const MIN_CHARAC_SLICE_LENGTH = 8;

// =============================================================================
// Site URL (for SEO, canonical URLs, etc.)
// =============================================================================

/**
 * Base URL for the site (used in SEO, sitemaps, canonical URLs).
 *
 * WHY process.env['...'] instead of process.env.X?
 * - Next.js requires bracket notation for client-side env vars
 * - Ensures proper tree-shaking and replacement at build time
 */
export const SITE_URL = process.env['NEXT_PUBLIC_SITE_URL'] || 'https://pulsai.live';

/**
 * Frontend build version metadata (explicit SoT for admin health visibility).
 * NEXT_PUBLIC_* is injected at build via next.config.
 */
const FRONTEND_APP_VERSION = process.env['NEXT_PUBLIC_APP_VERSION'] || '0.1.0';
const FRONTEND_BUILD_SHA = process.env['NEXT_PUBLIC_BUILD_SHA'] || '';

export const FRONTEND_RELEASE = FRONTEND_BUILD_SHA
  ? `${FRONTEND_APP_VERSION}+${FRONTEND_BUILD_SHA.slice(0, MIN_CHARAC_SLICE_LENGTH)}`
  : FRONTEND_APP_VERSION;

// =============================================================================
// API Base URL
// =============================================================================

/**
 * Base URL for all API requests.
 */
export const API_BASE_URL = process.env['NEXT_PUBLIC_API_URL'] || 'http://localhost:8000';

// =============================================================================
// Derived URLs
// =============================================================================

/**
 * API v1 base endpoint.
 */
export const API_V1_URL = `${API_BASE_URL}/api/v1`;

/**
 * Auth API endpoint.
 */

/**
 * AI API endpoint.
 */

/**
 * Admin API endpoint.
 */

/**
 * Signals API endpoint (GET latest, list, history, detail).
 * §5.4 + §12: Single SOT for signals API paths; no hardcoded /api/v1/signals in fetchers.
 */
export const SIGNALS_ENDPOINT = `${API_V1_URL}/signals`;

/**
 * The `governance_layout` this client asks GET /signals/{symbol}/history for: each book's
 * cert_levers / money_tier / money_reason sent ONCE in `books`, not repeated on every row.
 *
 * Measured 2026-09-21, those strings were 28-63% of the billed response on every timeframe with
 * data. The value is the backend's `SignalHistoryGovernanceLayout.BY_BOOK`; a contract test reads
 * the committed `openapi.json` and fails if the server stops enumerating it.
 */
export const SIGNAL_HISTORY_GOVERNANCE_LAYOUT_BY_BOOK = 'by_book';

/** Exchange connections API. */
export const EXCHANGES_ENDPOINT = `${API_V1_URL}/exchanges`;

/**
 * Trading API endpoint (modes, mode-selection, performance, automations).
 *
 * Epic B (RefactorHuge): manual paper/live order routes moved to FE-direct
 * (live-direct via HMAC); demo-only order routes moved under {@link DEMO_ENDPOINT}.
 */
export const TRADING_ENDPOINT = `${API_V1_URL}/trading`;

/** Demo trading API endpoint (demo-only: trades, orders, portfolio, reset). */
export const DEMO_ENDPOINT = `${API_V1_URL}/demo`;

// =============================================================================
// WebSocket URL
// =============================================================================

/**
 * Convert HTTP URL to WebSocket URL.
 *
 * WHY: WebSocket connections need ws:// or wss:// protocol.
 * This converts http://localhost:8000 -> ws://localhost:8000
 *
 * @param path - Optional path to append (e.g., '/ws/signals')
 * @returns WebSocket URL string
 */
export function getWsUrl(path = ''): string {
  return API_BASE_URL.replace(/^http/, 'ws') + path;
}

// =============================================================================
// Fetch URL resolution (Next.js `/api/v1` + `/api` rewrites → backend `/api/v1`)
// =============================================================================

/**
 * Whether browser fetches should use same-origin `/api/v1/...` (Next rewrites to backend).
 *
 * Vitest (jsdom + `VITEST`) keeps absolute `API_BASE_URL` URLs so tests stay stable.
 */
function shouldUseNextApiProxy(url: string): boolean {
  if (!url.startsWith('/api/v1/')) {
    return false;
  }
  if (typeof window === 'undefined') {
    return false;
  }
  if (typeof process !== 'undefined' && process.env['VITEST'] === 'true') {
    return false;
  }
  if (isLocalApiBaseUrl()) {
    return false;
  }

  return true;
}

function isLocalApiBaseUrl(): boolean {
  try {
    const base = new URL(API_BASE_URL);

    return base.hostname === 'localhost' || base.hostname === '127.0.0.1';
  } catch {
    return false;
  }
}

/**
 * Resolve relative API path (must start with `/`) for `fetch` / `EventSource`.
 *
 * Browser: keep `/api/v1/...` (Next `rewrites` `/api/v1/:path*` → `${API_BASE_URL}/api/v1/:path*`).
 * Server / Vitest: `API_BASE_URL` + path.
 */
function resolveFetchUrlPath(path: string): string {
  if (shouldUseNextApiProxy(path)) {
    return path;
  }

  return `${API_BASE_URL}${path}`;
}

/**
 * Resolve URL for `fetch` / `EventSource`.
 *
 * - Relative `/api/v1/...`: same as {@link resolveFetchUrlPath}.
 * - Absolute `API_BASE_URL` + `/api/v1/...`: treated like the relative path (SoT for fetchers that
 *   build URLs from `SIGNALS_ENDPOINT` / `EXCHANGES_ENDPOINT`, which embed the base).
 * - Other absolute URLs: returned unchanged (e.g. CDNs, third parties).
 */
export function resolveFetchUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      const resolved = new URL(url);
      const base = new URL(API_BASE_URL);

      if (resolved.origin === base.origin) {
        const pathAndQuery = `${resolved.pathname}${resolved.search}`;
        const isV1Api = pathAndQuery === '/api/v1' || pathAndQuery.startsWith('/api/v1/');

        if (isV1Api) {
          return resolveFetchUrlPath(pathAndQuery);
        }
      }
    } catch {
      /* malformed URL */
    }

    return url;
  }

  return resolveFetchUrlPath(url);
}

/**
 * Resolve URL for browser ``EventSource`` (SSE).
 *
 * Unlike ``fetch``, ``EventSource`` does not reliably send cookies on cross-origin
 * requests (e.g. ``localhost:3000`` → ``localhost:8000``). In the browser we always
 * keep ``/api/v1/...`` same-origin so HttpOnly session cookies reach the API via
 * Next rewrites — local dev and production.
 */
export function resolveEventStreamUrl(pathAndQuery: string): string {
  let path = pathAndQuery;

  if (path.startsWith('http://') || path.startsWith('https://')) {
    try {
      const resolved = new URL(path);
      const base = new URL(API_BASE_URL);

      if (resolved.origin === base.origin) {
        path = `${resolved.pathname}${resolved.search}`;
      } else {
        return pathAndQuery;
      }
    } catch {
      return resolveFetchUrl(pathAndQuery);
    }
  }

  if (!path.startsWith('/api/v1/')) {
    return resolveFetchUrl(pathAndQuery);
  }

  if (typeof window === 'undefined') {
    return resolveFetchUrl(path);
  }

  if (typeof process !== 'undefined' && process.env['VITEST'] === 'true') {
    return resolveFetchUrl(path);
  }

  return path;
}
