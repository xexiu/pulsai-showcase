import {
  HTTP_IDEMPOTENCY_TOKEN_RADIX,
  HTTP_IDEMPOTENCY_TOKEN_SLICE_START,
} from '@/utils/constants/httpIdempotency';

/**
 * Returns a fresh idempotency token per call (UUID when available, else timestamp + random).
 */
export function buildHttpIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto;

  if (cryptoApi != null && typeof cryptoApi.randomUUID === 'function') {
    return cryptoApi.randomUUID();
  }

  return `${Date.now()}-${Math.random()
    .toString(HTTP_IDEMPOTENCY_TOKEN_RADIX)
    .slice(HTTP_IDEMPOTENCY_TOKEN_SLICE_START)}`;
}
