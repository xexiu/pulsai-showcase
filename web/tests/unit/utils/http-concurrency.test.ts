// @vitest-environment node

import { describe, expect, it } from 'vitest';

import {
  HTTP_STATUS_PRECONDITION_FAILED,
  ifMatchRequestHeaders,
  isStaleResourceError,
  readEtagFromResponse,
  StaleResourceError,
  assertResponseNotStale,
} from '@/utils/http-concurrency';

describe('http-concurrency', () => {
  it('readEtagFromResponse returns trimmed etag header', () => {
    const response = new Response(null, { headers: { etag: ' "abc123" ' } });

    expect(readEtagFromResponse(response)).toBe('"abc123"');
  });

  it('ifMatchRequestHeaders omits header when etag is null', () => {
    expect(ifMatchRequestHeaders(null)).toBeUndefined();
  });

  it('ifMatchRequestHeaders sets If-Match when etag is present', () => {
    expect(ifMatchRequestHeaders('"deadbeef"')).toEqual({ 'If-Match': '"deadbeef"' });
  });

  it('assertResponseNotStale throws StaleResourceError on 412', () => {
    const response = new Response(null, { status: HTTP_STATUS_PRECONDITION_FAILED });

    expect(() => assertResponseNotStale(response)).toThrow(StaleResourceError);
    expect(isStaleResourceError(new StaleResourceError())).toBe(true);
  });
});
