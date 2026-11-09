// @vitest-environment node
/**
 * Direct module tests for api-token-refresh (deduped refresh + await helper).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/proactive-session-refresh', () => ({
  refreshSessionAndReschedule: vi.fn(),
}));

vi.mock('@/services/auth', async (importOriginal) => {
  const actual = await importOriginal();

  return {
    ...(actual as Record<string, unknown>),
    getStoredTokens: vi.fn(() => null),
  };
});

describe('api-token-refresh module', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
  });

  it('refreshTokenIfNeeded delegates to refreshSessionAndReschedule', async () => {
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');
    const { refreshTokenIfNeeded } = await import('@/services/api/api-token-refresh');

    vi.mocked(refreshSessionAndReschedule).mockResolvedValueOnce(true);

    const result = await refreshTokenIfNeeded();

    expect(result).toBe(true);
    expect(refreshSessionAndReschedule).toHaveBeenCalledTimes(1);
  });

  it('awaitPendingTokenRefresh waits for in-flight refresh', async () => {
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');
    const { awaitPendingTokenRefresh, refreshTokenIfNeeded } =
      await import('@/services/api/api-token-refresh');

    let resolveRefresh!: (value: boolean) => void;
    const refreshGate = new Promise<boolean>((resolve) => {
      resolveRefresh = resolve;
    });

    vi.mocked(refreshSessionAndReschedule).mockReturnValueOnce(refreshGate);

    const refreshTask = refreshTokenIfNeeded();
    const awaitTask = awaitPendingTokenRefresh();

    resolveRefresh(true);
    await refreshTask;
    await awaitTask;

    expect(refreshSessionAndReschedule).toHaveBeenCalledTimes(1);
  });

  it('awaitPendingTokenRefresh swallows refresh failure', async () => {
    const { refreshSessionAndReschedule } = await import('@/services/proactive-session-refresh');
    const { awaitPendingTokenRefresh, refreshTokenIfNeeded } =
      await import('@/services/api/api-token-refresh');

    vi.mocked(refreshSessionAndReschedule).mockResolvedValueOnce(false);

    const refreshTask = refreshTokenIfNeeded();

    await expect(awaitPendingTokenRefresh()).resolves.toBeUndefined();
    await expect(refreshTask).resolves.toBe(false);
  });
});
