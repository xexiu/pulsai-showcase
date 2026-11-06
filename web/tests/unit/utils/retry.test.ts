/**
 * Centralized retry helpers — behavior tests.
 *
 * @see apps/web/src/utils/retry.ts
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { executeWithRetry, fetchWithRetry, isRetryableError } from '@/utils/retry';

describe('isRetryableError', () => {
  it('treats AbortError as retryable', () => {
    const err = new Error('aborted');

    err.name = 'AbortError';

    expect(isRetryableError(err)).toBe(true);
  });

  it('treats fetch TypeError as retryable', () => {
    const err = new TypeError('Failed to fetch');

    expect(isRetryableError(err)).toBe(true);
  });

  it('treats timeout/network/failed-to-fetch message errors as retryable', () => {
    expect(isRetryableError(new Error('Connection TIMEOUT'))).toBe(true);
    expect(isRetryableError(new Error('Network error'))).toBe(true);
    expect(isRetryableError(new Error('Failed to fetch (opaque)'))).toBe(true);
  });

  it('returns false for non-Error values', () => {
    expect(isRetryableError('timeout')).toBe(false);
    expect(isRetryableError(null)).toBe(false);
    expect(isRetryableError({ message: 'timeout' })).toBe(false);
  });

  it('returns false for Error without retryable signals', () => {
    expect(isRetryableError(new Error('HTTP 400'))).toBe(false);
  });

  it('returns false for TypeError when message does not mention fetch', () => {
    expect(isRetryableError(new TypeError('cannot read properties of undefined'))).toBe(false);
  });
});

describe('executeWithRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.mocked(Math.random).mockRestore();
    vi.useRealTimers();
  });

  it('returns the result when the first attempt succeeds', async () => {
    const fn = vi.fn().mockResolvedValue('ok');

    const pending = executeWithRetry(fn, { maxRetries: 2 });

    await expect(pending).resolves.toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('retries on retryable errors then returns the resolved value', async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValueOnce('recovered');

    const pending = executeWithRetry(fn, {
      maxRetries: 2,
      baseDelayMs: 1000,
      maxDelayMs: 8000,
    });

    await vi.advanceTimersByTimeAsync(0);
    const resultPromise = pending;

    await vi.advanceTimersByTimeAsync(1000);
    await expect(resultPromise).resolves.toBe('recovered');
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('stops when retryCondition returns false and propagates the error', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('client'));

    await expect(
      executeWithRetry(fn, {
        maxRetries: 3,
        retryCondition: () => false,
      })
    ).rejects.toThrow('client');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('throws after exhausting maxRetries on retryable failures', async () => {
    const err = new Error('timeout');

    const fn = vi.fn().mockRejectedValue(err);

    const pending = executeWithRetry(fn, {
      maxRetries: 1,
      baseDelayMs: 500,
      maxDelayMs: 8000,
    });

    const assertion = expect(pending).rejects.toBe(err);

    await vi.advanceTimersByTimeAsync(500);
    await assertion;
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('caps backoff at maxDelayMs', async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new Error('timeout'))
      .mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValue('ok');

    const pending = executeWithRetry(fn, {
      maxRetries: 3,
      baseDelayMs: 10_000,
      maxDelayMs: 100,
    });

    await vi.advanceTimersByTimeAsync(100);
    await vi.advanceTimersByTimeAsync(100);
    await expect(pending).resolves.toBe('ok');
  });

  it('does not wrap the task in a timeout race when timeoutMs is omitted', async () => {
    const fn = vi.fn().mockResolvedValue(42);

    await expect(executeWithRetry(fn, {})).resolves.toBe(42);
  });

  it('does not wrap the task when timeoutMs is zero', async () => {
    const fn = vi.fn().mockResolvedValue(7);

    await expect(executeWithRetry(fn, { timeoutMs: 0 })).resolves.toBe(7);
  });

  it('rejects when per-attempt timeout fires before the task resolves', async () => {
    const fn = vi.fn(
      () =>
        new Promise<string>(() => {
          /* never resolves */
        })
    );

    const pending = executeWithRetry(fn, {
      maxRetries: 0,
      timeoutMs: 200,
    });

    const assertion = expect(pending).rejects.toThrow('Request timed out after 200ms');

    await vi.advanceTimersByTimeAsync(200);
    await assertion;
  });
});

describe('fetchWithRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.mocked(Math.random).mockRestore();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('returns ok Response and clears the abort timer', async () => {
    const response = new Response('body', { status: 200 });

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => Promise.resolve(response))
    );

    const pending = fetchWithRetry('https://example.com/api', undefined, {
      maxRetries: 0,
      timeoutMs: 5000,
    });

    await vi.advanceTimersByTimeAsync(0);
    const res = await pending;

    expect(res.ok).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      'https://example.com/api',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );

    vi.unstubAllGlobals();
  });

  it('does not retry on HTTP error by default (not classified as retryable)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('err', { status: 503 })));

    await expect(
      fetchWithRetry('https://example.com/x', undefined, {
        maxRetries: 2,
        timeoutMs: 10_000,
      })
    ).rejects.toThrow('HTTP 503');
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);

    vi.unstubAllGlobals();
  });

  it('retries HTTP failures when retryCondition opts in', async () => {
    const ok = new Response('ok', { status: 200 });

    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(new Response('err', { status: 503 }))
        .mockResolvedValueOnce(ok)
    );

    const pending = fetchWithRetry('https://example.com/x', undefined, {
      maxRetries: 1,
      baseDelayMs: 100,
      maxDelayMs: 8000,
      timeoutMs: 10_000,
      retryCondition: (e) => e instanceof Error && e.message.startsWith('HTTP'),
    });

    const assertion = expect(pending).resolves.toMatchObject({ status: 200 });

    await vi.advanceTimersByTimeAsync(100);
    await assertion;
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2);

    vi.unstubAllGlobals();
  });

  it('maps AbortError from fetch to a timeout message', async () => {
    const abortErr = new Error('Aborted');

    abortErr.name = 'AbortError';

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortErr));

    const pending = fetchWithRetry('https://example.com/y', undefined, {
      maxRetries: 0,
      timeoutMs: 3000,
    });

    await expect(pending).rejects.toThrow('Request timed out after 3000ms');

    vi.unstubAllGlobals();
  });

  it('aborts the internal controller when the external signal aborts', async () => {
    const ac = new AbortController();
    let innerSignal: AbortSignal | undefined;

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        const sig = init?.signal;

        innerSignal = sig ?? undefined;

        return new Promise<Response>((_, reject) => {
          if (!sig) {
            reject(new Error('missing signal'));

            return;
          }

          sig.addEventListener('abort', () => {
            reject(new DOMException('Aborted', 'AbortError'));
          });
        });
      })
    );

    const pending = fetchWithRetry(
      'https://example.com/z',
      { signal: ac.signal },
      {
        maxRetries: 0,
        timeoutMs: 60_000,
      }
    );

    await Promise.resolve();
    ac.abort('user-cancel');
    await expect(pending).rejects.toThrow('Aborted');

    expect(innerSignal?.aborted).toBe(true);

    vi.unstubAllGlobals();
  });
});
