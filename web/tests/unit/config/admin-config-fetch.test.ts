// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { patchAdminConfigJson } from '@/config/admin-config-fetch';
import { HTTP_IDEMPOTENCY_KEY_HEADER } from '@/utils/constants/httpIdempotency';

const mockAppFetch = vi.fn();

vi.mock('@/services/api', () => ({
  appFetch: (...args: unknown[]) => mockAppFetch(...args),
}));

describe('admin-config-fetch idempotency', () => {
  beforeEach(() => {
    mockAppFetch.mockReset();
    vi.stubGlobal('crypto', { randomUUID: () => 'test-idem-key' });
  });

  it('patchAdminConfigJson sends Idempotency-Key and If-Match', async () => {
    mockAppFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ etag: '"new-etag"' }),
      json: () => Promise.resolve({ paused: false }),
    });

    await patchAdminConfigJson(
      '/api/v1/admin/system-controls',
      { paused: false },
      { ifMatch: '"old-etag"', sendIdempotency: true, idempotencyKey: 'slice-key' },
      'Failed'
    );

    const call = mockAppFetch.mock.calls[0]?.[0] as { headers?: Record<string, string> };

    expect(call.headers).toEqual({
      'If-Match': '"old-etag"',
      [HTTP_IDEMPOTENCY_KEY_HEADER]: 'slice-key',
    });
  });
});
