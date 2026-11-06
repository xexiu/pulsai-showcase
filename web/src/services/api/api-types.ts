/**
 * Options for appFetch. Single place for auth, retry, timeout, and abort.
 * @see docs/04-structural/DATA_LAYER_AND_CHART_SOT.md §7
 */
export interface AppFetchOptions {
  /** Request URL (relative to API_BASE_URL if not absolute). */
  url: string;
  /** HTTP method (default GET). */
  method?: RequestInit['method'];
  /** AbortSignal for cancellation (e.g. from TanStack Query). */
  signal?: AbortSignal | undefined;
  /** If true, use authenticatedFetch (cookies, refresh-on-401, CSRF on mutations). */
  auth?: boolean;
  /** If true, use fetchWithRetry (timeout, retries). Use for public or resilient GETs. */
  retry?: boolean;
  /** Timeout per attempt in ms when retry is true. */
  timeoutMs?: number;
  /** Max retries when retry is true. */
  maxRetries?: number;
  /** Request body. */
  body?: RequestInit['body'];
  /** Additional headers. */
  headers?: HeadersInit;
}
