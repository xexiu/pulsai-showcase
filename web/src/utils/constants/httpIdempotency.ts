/**
 * HTTP idempotency constants — aligned with BE `http_idempotency.py`.
 */

/** Request header for idempotent mutation retries. */
export const HTTP_IDEMPOTENCY_KEY_HEADER = 'Idempotency-Key' as const;

/** Max stored key length (BE receipt table). */
export const HTTP_IDEMPOTENCY_KEY_MAX_LEN = 128;

/** Response header when the server replays a prior result. */
export const HTTP_HEADER_IDEMPOTENT_REPLAYED = 'X-Idempotent-Replayed' as const;

export const HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE = 'true' as const;

/** Radix for Math.random fallback token when crypto.randomUUID is unavailable. */
export const HTTP_IDEMPOTENCY_TOKEN_RADIX = 36;

/** Strip leading chars from toString(36) for entropy tail. */
export const HTTP_IDEMPOTENCY_TOKEN_SLICE_START = 2;
