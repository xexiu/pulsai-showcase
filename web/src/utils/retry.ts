/**
 * Centralized retry logic for API and network calls.
 *
 * WHY?
 * - Single source of truth for retry strategy (avoids ad-hoc retries per hook).
 * - Handles temporary BE unavailability / timeouts (e.g. "Connection timeout - OHLCV API not responding").
 * - Pattern aligned with reference: Desktop/projects/Amphora/aaxaa (RetryUtility + _service).
 *
 * Use fetchWithRetry for GET requests that should retry on timeout/network errors.
 * Use executeWithRetry for custom async work with retries.
 */

export interface RetryOptions {
  /** Max retry attempts after initial failure (default 3 = 1 initial + 3 retries). */
  maxRetries?: number;
  /** Base delay in ms between attempts; exponential backoff uses this (default 1500). */
  baseDelayMs?: number;
  /** Max delay cap in ms (default 8000). */
  maxDelayMs?: number;
  /** Timeout per attempt in ms; no per-attempt timeout if undefined. */
  timeoutMs?: number;
  /** Return true to retry this error (default: retry on timeout/network/5xx). */
  retryCondition?: (error: unknown) => boolean;
}

const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_BASE_DELAY_MS = 1500;
const DEFAULT_MAX_DELAY_MS = 8000;
/** ±20% jitter on delay to avoid thundering herd. */
const JITTER_FACTOR = 0.2;

/** True for errors that are worth retrying (timeout, network, server unavailable). */
export function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    if (error.name === 'AbortError') return true;
    if (error.name === 'TypeError' && error.message.includes('fetch')) return true;

    const msg = error.message.toLowerCase();

    if (msg.includes('timeout') || msg.includes('network') || msg.includes('failed to fetch')) {
      return true;
    }
  }

  return false;
}

/**
 * Run an async function with retries and optional per-attempt timeout.
 * Uses exponential backoff with jitter between attempts.
 */
export async function executeWithRetry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxRetries = DEFAULT_MAX_RETRIES,
    baseDelayMs = DEFAULT_BASE_DELAY_MS,
    maxDelayMs = DEFAULT_MAX_DELAY_MS,
    timeoutMs,
    retryCondition = isRetryableError,
  } = options;

  let lastError: unknown;
  let attempt = 0;

  const run = async (): Promise<T> => {
    const task = fn();

    if (timeoutMs !== undefined && timeoutMs > 0) {
      return Promise.race([
        task,
        new Promise<T>((_, reject) => {
          setTimeout(() => reject(new Error(`Request timed out after ${timeoutMs}ms`)), timeoutMs);
        }),
      ]);
    }

    return task;
  };

  while (attempt <= maxRetries) {
    try {
      return await run();
    } catch (error: unknown) {
      lastError = error;
      attempt++;

      if (attempt > maxRetries || !retryCondition(error)) {
        throw error;
      }

      const delay = Math.min(baseDelayMs * 2 ** (attempt - 1), maxDelayMs);
      const jitter = delay * JITTER_FACTOR * (Math.random() * 2 - 1);

      await new Promise((resolve) => setTimeout(resolve, Math.max(0, delay + jitter)));
    }
  }

  throw lastError;
}

const DEFAULT_FETCH_TIMEOUT_MS = 10000;

export interface FetchWithRetryOptions extends RetryOptions {
  /** Timeout per attempt in ms (default 10000). */
  timeoutMs?: number;
}

/**
 * Fetch with timeout per attempt and retries on timeout/network errors.
 * Single source of truth for resilient GET (e.g. OHLCV) when BE may be temporarily down.
 * Supports external signal (e.g. from hook) so unmount/param-change can cancel.
 */
export async function fetchWithRetry(
  url: string,
  init?: RequestInit,
  options: FetchWithRetryOptions = {}
): Promise<Response> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_FETCH_TIMEOUT_MS;

  return executeWithRetry(
    async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      if (init?.signal) {
        init.signal.addEventListener('abort', () => controller.abort(init.signal!.reason));
      }

      try {
        const response = await fetch(url, { ...init, signal: controller.signal });

        clearTimeout(timeoutId);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        return response;
      } catch (err) {
        clearTimeout(timeoutId);

        if (err instanceof Error && err.name === 'AbortError') {
          throw new Error(`Request timed out after ${timeoutMs}ms`);
        }

        throw err;
      }
    },
    {
      maxRetries: options.maxRetries ?? DEFAULT_MAX_RETRIES,
      baseDelayMs: options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS,
      maxDelayMs: options.maxDelayMs ?? DEFAULT_MAX_DELAY_MS,
      retryCondition: options.retryCondition ?? isRetryableError,
    }
  );
}
