// @vitest-environment node
/**
 * Direct module tests for api-verbs (HTTP verb helpers).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockAuthenticatedFetch = vi.fn();

vi.mock('@/services/api/api-authenticated-fetch', () => ({
  authenticatedFetch: (...args: unknown[]) => mockAuthenticatedFetch(...args),
}));

import {
  authenticatedDelete,
  authenticatedGet,
  authenticatedPost,
  authenticatedPut,
} from '@/services/api/api-verbs';

describe('api-verbs', () => {
  beforeEach(() => {
    mockAuthenticatedFetch.mockReset();
    mockAuthenticatedFetch.mockResolvedValue(new Response('{}', { status: 200 }));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('authenticatedGet uses GET without body', async () => {
    const controller = new AbortController();

    await authenticatedGet('/api/v1/foo', controller.signal);

    expect(mockAuthenticatedFetch).toHaveBeenCalledWith('/api/v1/foo', {
      method: 'GET',
      signal: controller.signal,
    });
  });

  it('authenticatedPost serializes JSON body', async () => {
    const body = { symbol: 'BTC/USDT' };

    await authenticatedPost('/api/v1/train', body);

    expect(mockAuthenticatedFetch).toHaveBeenCalledWith('/api/v1/train', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  });

  it('authenticatedPut serializes JSON body and forwards signal', async () => {
    const controller = new AbortController();
    const body = { enabled: true };

    await authenticatedPut('/api/v1/settings', body, controller.signal);

    expect(mockAuthenticatedFetch).toHaveBeenCalledWith('/api/v1/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  });

  it('authenticatedDelete uses DELETE', async () => {
    await authenticatedDelete('/api/v1/resource/1');

    expect(mockAuthenticatedFetch).toHaveBeenCalledWith('/api/v1/resource/1', {
      method: 'DELETE',
    });
  });
});
