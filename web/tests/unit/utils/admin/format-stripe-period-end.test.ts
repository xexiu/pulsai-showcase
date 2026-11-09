// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/utils/formatters', () => ({
  formatDateTime: vi.fn((d: Date) => `mock:${d.getTime()}`),
}));

import { formatStripePeriodEndUnix } from '@/utils/admin/format-stripe-period-end';
import { formatDateTime } from '@/utils/formatters';

describe('formatStripePeriodEndUnix', () => {
  beforeEach(() => {
    vi.mocked(formatDateTime).mockClear();
  });

  it('returns empty string for null', () => {
    expect(formatStripePeriodEndUnix(null)).toBe('');
    expect(formatDateTime).not.toHaveBeenCalled();
  });

  it('converts unix seconds to ms before delegating to formatDateTime', () => {
    expect(formatStripePeriodEndUnix(1)).toBe('mock:1000');
    expect(formatDateTime).toHaveBeenCalledTimes(1);
    const firstCall = vi.mocked(formatDateTime).mock.calls[0];

    expect(firstCall).toBeDefined();
    const arg = firstCall?.[0] as Date;

    expect(arg.getTime()).toBe(1000);
  });
});
