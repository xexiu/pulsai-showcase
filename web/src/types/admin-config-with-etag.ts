/**
 * Admin runtime config fetch/mutation results with optimistic-concurrency ETag.
 *
 * @see docs/02-technical/API_SPECIFICATION.md — ETag / If-Match on admin configs
 */

export type AdminConfigWithEtag<T> = {
  data: T;
  /** Strong ETag from the latest GET or successful mutation response. */
  etag: string | null;
};

export type AdminConfigMutationOptions = {
  signal?: AbortSignal;
  ifMatch?: string | null;
  /** When true, sends `Idempotency-Key` (only endpoints with BE idempotency support). */
  sendIdempotency?: boolean;
  /** Used with `sendIdempotency`; fresh key generated when omitted. */
  idempotencyKey?: string | null;
};
