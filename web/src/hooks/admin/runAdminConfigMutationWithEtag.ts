import type { AdminConfigWithEtag } from '@/types/admin-config-with-etag';
import { isStaleResourceError } from '@/utils/http-concurrency';

import type { QueryClient, QueryKey } from '@tanstack/react-query';

export type RunAdminConfigMutationWithEtagParams<T> = {
  execute: (ifMatch: string | null) => Promise<AdminConfigWithEtag<T>>;
  getIfMatch: () => string | null;
  setFromResult: (result: AdminConfigWithEtag<T>) => void;
  queryClient: QueryClient;
  queryKey: QueryKey;
};

/**
 * Runs an admin config mutation with If-Match, auto-recovering from a stale validator.
 *
 * A stale 412 can come from a parallel tab bumping the resource OR from a compressing edge
 * (Cloudflare) rewriting / edge-rejecting the conditional `If-Match` before it reaches the origin.
 * On the first stale conflict we refetch the current ETag and retry the mutation ONCE silently — so
 * the toggle "just works" for the common single-admin case. Only if the retry ALSO conflicts (a
 * genuine concurrent write) do we invalidate the cache and surface the error to the caller.
 */
export async function runAdminConfigMutationWithEtag<T>(
  params: RunAdminConfigMutationWithEtagParams<T>
): Promise<T> {
  try {
    const result = await params.execute(params.getIfMatch());

    params.setFromResult(result);

    return result.data;
  } catch (error) {
    if (!isStaleResourceError(error)) {
      throw error;
    }

    // Refetch the live ETag (the GET's queryFn calls setFromResult), then retry once.
    await params.queryClient.refetchQueries({ queryKey: params.queryKey });

    try {
      const retried = await params.execute(params.getIfMatch());

      params.setFromResult(retried);

      return retried.data;
    } catch (retryError) {
      if (isStaleResourceError(retryError)) {
        await params.queryClient.invalidateQueries({ queryKey: params.queryKey });
      }

      throw retryError;
    }
  }
}
