import { buildHttpIdempotencyKey } from '@/utils/build-http-idempotency-key';

/**
 * Returns a fresh idempotency token per call (UUID when available, else timestamp + random).
 */
export function buildPlaceOrderIdempotencyKey(): string {
  return buildHttpIdempotencyKey();
}
