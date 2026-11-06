// =============================================================================
// API Service - Authenticated Fetch Utilities
// =============================================================================
//
// WHY THIS FILE?
// - Product and admin hooks need same-origin fetches with session cookies
// - Backend accepts HttpOnly access cookie and/or Authorization Bearer; browser flow is cookie-first
// - 401 triggers a single coordinated refresh (see refreshTokenIfNeeded), then one retry
//
// FIX (2026-01-29): Created to resolve 401 bug on admin pages
// ENHANCEMENT (2026-02-05): Reactive session refresh after 401 (no client-visible access expiry)
// =============================================================================

export type { AppFetchOptions } from '@/services/api/api-types';
export { AUTH_ERROR_KEYS, isAuthErrorKey } from '@/services/api/api-auth-errors';
export { awaitPendingTokenRefresh, refreshTokenIfNeeded } from '@/services/api/api-token-refresh';
export { resolveEventStreamUrl } from '@/services/api/api-transport';
export { appFetch, fetchWithOptionalAuth } from '@/services/api/api-app-fetch';
export { authenticatedFetch } from '@/services/api/api-authenticated-fetch';
export {
  authenticatedGet,
  authenticatedPost,
  authenticatedPut,
  authenticatedDelete,
} from '@/services/api/api-verbs';
