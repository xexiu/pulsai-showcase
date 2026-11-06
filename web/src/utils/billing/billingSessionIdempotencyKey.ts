import { buildHttpIdempotencyKey } from '@/utils/build-http-idempotency-key';

function hasSessionStorage(): boolean {
  return typeof sessionStorage !== 'undefined';
}

/**
 * Shared sessionStorage-backed idempotency key (SSR-safe).
 * Domain modules pass stable storage keys / prefixes.
 */
export function resolveBillingSessionIdempotencyKey(storageKey: string): string {
  if (!hasSessionStorage()) {
    return buildHttpIdempotencyKey();
  }

  const existing = sessionStorage.getItem(storageKey);

  if (existing != null && existing.trim() !== '') {
    return existing;
  }

  const fresh = buildHttpIdempotencyKey();

  sessionStorage.setItem(storageKey, fresh);

  return fresh;
}

export function clearBillingSessionIdempotencyKey(storageKey: string): void {
  if (!hasSessionStorage()) {
    return;
  }

  sessionStorage.removeItem(storageKey);
}

export function clearBillingSessionIdempotencyKeysByPrefix(prefix: string): void {
  if (!hasSessionStorage()) {
    return;
  }

  const keysToRemove: string[] = [];

  for (let index = 0; index < sessionStorage.length; index += 1) {
    const key = sessionStorage.key(index);

    if (key != null && key.startsWith(prefix)) {
      keysToRemove.push(key);
    }
  }

  for (const key of keysToRemove) {
    sessionStorage.removeItem(key);
  }
}
