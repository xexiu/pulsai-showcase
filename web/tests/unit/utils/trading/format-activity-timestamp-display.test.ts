// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { TRADING_BALANCE_UNAVAILABLE_MARK } from '@/utils/constants/trading';
import { formatActivityTimestampDisplay } from '@/utils/trading/format-activity-timestamp-display';

describe('formatActivityTimestampDisplay', () => {
  it('returns em dash for empty input', () => {
    expect(formatActivityTimestampDisplay('')).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
    expect(formatActivityTimestampDisplay(undefined)).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
    expect(formatActivityTimestampDisplay(null)).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
  });

  it('returns formatted string for valid ISO', () => {
    const s = formatActivityTimestampDisplay('2026-01-15T12:00:00.000Z');

    expect(s).not.toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
    expect(s.length).toBeGreaterThan(4);
  });
});
