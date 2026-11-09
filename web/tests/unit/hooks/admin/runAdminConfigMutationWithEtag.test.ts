// @vitest-environment node
import { QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { runAdminConfigMutationWithEtag } from '@/hooks/admin/runAdminConfigMutationWithEtag';
import { StaleResourceError } from '@/utils/http-concurrency';

describe('runAdminConfigMutationWithEtag', () => {
  const queryKey = ['admin-config', 'test'] as const;
  let queryClient: QueryClient;
  const setFromResult = vi.fn();
  const getIfMatch = vi.fn(() => '"etag-1"');

  beforeEach(() => {
    queryClient = new QueryClient();
    vi.spyOn(queryClient, 'invalidateQueries');
    vi.spyOn(queryClient, 'refetchQueries');
    setFromResult.mockClear();
    getIfMatch.mockClear();
    getIfMatch.mockReturnValue('"etag-1"');
  });

  it('returns data and updates etag on success', async () => {
    const execute = vi.fn(async (ifMatch: string | null) => {
      expect(ifMatch).toBe('"etag-1"');

      return { data: { ok: true }, etag: '"etag-2"' };
    });

    const out = await runAdminConfigMutationWithEtag({
      execute,
      getIfMatch,
      setFromResult,
      queryClient,
      queryKey,
    });

    expect(out).toEqual({ ok: true });
    expect(setFromResult).toHaveBeenCalledWith({ data: { ok: true }, etag: '"etag-2"' });
    expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
  });

  it('refetches the etag and retries once, succeeding silently after a stale conflict', async () => {
    const execute = vi
      .fn()
      .mockRejectedValueOnce(new StaleResourceError()) // first attempt: stale (e.g. edge-rewritten ETag)
      .mockResolvedValueOnce({ data: { ok: true }, etag: '"etag-fresh"' }); // retry after refetch: ok

    const out = await runAdminConfigMutationWithEtag({
      execute,
      getIfMatch,
      setFromResult,
      queryClient,
      queryKey,
    });

    expect(out).toEqual({ ok: true });
    expect(execute).toHaveBeenCalledTimes(2); // retried once
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({ queryKey }); // refreshed the etag
    expect(setFromResult).toHaveBeenCalledWith({ data: { ok: true }, etag: '"etag-fresh"' });
    expect(queryClient.invalidateQueries).not.toHaveBeenCalled(); // no toast — recovered silently
  });

  it('rethrows + invalidates only when the retry also conflicts (genuine concurrent write)', async () => {
    const execute = vi.fn(async () => {
      throw new StaleResourceError();
    });

    await expect(
      runAdminConfigMutationWithEtag({
        execute,
        getIfMatch,
        setFromResult,
        queryClient,
        queryKey,
      })
    ).rejects.toBeInstanceOf(StaleResourceError);

    expect(execute).toHaveBeenCalledTimes(2); // tried, refetched, retried
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({ queryKey });
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey });
    expect(setFromResult).not.toHaveBeenCalled();
  });
});
