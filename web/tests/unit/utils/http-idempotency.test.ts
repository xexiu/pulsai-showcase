// @vitest-environment node

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  HTTP_HEADER_IDEMPOTENT_REPLAYED,
  HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE,
  HTTP_IDEMPOTENCY_KEY_HEADER,
} from '@/utils/constants/httpIdempotency';
import {
  adminMutationRequestHeaders,
  idempotencyRequestHeaders,
  readIdempotentReplayedFromResponse,
} from '@/utils/http-idempotency';

describe('http-idempotency', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('idempotencyRequestHeaders generates a key when none is provided', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'generated-key' });

    expect(idempotencyRequestHeaders()).toEqual({
      [HTTP_IDEMPOTENCY_KEY_HEADER]: 'generated-key',
    });
  });

  it('idempotencyRequestHeaders uses explicit key when provided', () => {
    expect(idempotencyRequestHeaders('client-key-1')).toEqual({
      [HTTP_IDEMPOTENCY_KEY_HEADER]: 'client-key-1',
    });
  });

  it('adminMutationRequestHeaders merges If-Match and Idempotency-Key', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'idem-1' });

    expect(
      adminMutationRequestHeaders({
        ifMatch: '"etag-a"',
        idempotencyKey: 'explicit-idem',
      })
    ).toEqual({
      'If-Match': '"etag-a"',
      [HTTP_IDEMPOTENCY_KEY_HEADER]: 'explicit-idem',
    });
  });

  it('readIdempotentReplayedFromResponse is true when replay header is set', () => {
    const response = new Response(null, {
      headers: { [HTTP_HEADER_IDEMPOTENT_REPLAYED]: HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE },
    });

    expect(readIdempotentReplayedFromResponse(response)).toBe(true);
  });
});
