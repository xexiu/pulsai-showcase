// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';

import { buildPlaceOrderIdempotencyKey } from '@/utils/trading/build-place-order-idempotency-key';

describe('buildPlaceOrderIdempotencyKey', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('uses crypto.randomUUID when available', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'uuid-test-1234' });

    expect(buildPlaceOrderIdempotencyKey()).toBe('uuid-test-1234');
  });

  it('falls back to timestamp + random token when randomUUID is missing', () => {
    vi.stubGlobal('crypto', {});

    const fixedRandom = 0.123456789;

    vi.spyOn(Math, 'random').mockReturnValue(fixedRandom);
    vi.spyOn(Date, 'now').mockReturnValue(1_700_000_000_000);

    const key = buildPlaceOrderIdempotencyKey();

    expect(key.startsWith('1700000000000-')).toBe(true);
    expect(key.length).toBeGreaterThan(16);
  });
});
