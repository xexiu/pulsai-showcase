import { afterEach, describe, expect, it } from 'vitest';

import {
  clearBillingSessionIdempotencyKey,
  clearBillingSessionIdempotencyKeysByPrefix,
  resolveBillingSessionIdempotencyKey,
} from '@/utils/billing/billingSessionIdempotencyKey';

const KEY_A = 'pulsai:billing:test:a';
const KEY_B = 'pulsai:billing:test:b';
const PREFIX = 'pulsai:billing:test:';

describe('billingSessionIdempotencyKey', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('returns the same key for the same storage key', () => {
    const first = resolveBillingSessionIdempotencyKey(KEY_A);
    const second = resolveBillingSessionIdempotencyKey(KEY_A);

    expect(second).toBe(first);
  });

  it('clear removes a single key', () => {
    const first = resolveBillingSessionIdempotencyKey(KEY_A);

    clearBillingSessionIdempotencyKey(KEY_A);

    const second = resolveBillingSessionIdempotencyKey(KEY_A);

    expect(second).not.toBe(first);
  });

  it('clearByPrefix removes all keys with the prefix', () => {
    const a = resolveBillingSessionIdempotencyKey(KEY_A);
    const b = resolveBillingSessionIdempotencyKey(KEY_B);

    clearBillingSessionIdempotencyKeysByPrefix(PREFIX);

    const aAfter = resolveBillingSessionIdempotencyKey(KEY_A);
    const bAfter = resolveBillingSessionIdempotencyKey(KEY_B);

    expect(aAfter).not.toBe(a);
    expect(bAfter).not.toBe(b);
  });
});
