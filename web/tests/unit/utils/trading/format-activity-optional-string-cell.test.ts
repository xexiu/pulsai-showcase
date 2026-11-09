// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { TRADING_BALANCE_UNAVAILABLE_MARK } from '@/utils/constants/trading';
import { formatActivityOptionalStringCell } from '@/utils/trading/format-activity-optional-string-cell';

describe('formatActivityOptionalStringCell', () => {
  it('returns em dash for nullish or empty', () => {
    expect(formatActivityOptionalStringCell(null)).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
    expect(formatActivityOptionalStringCell(undefined)).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
    expect(formatActivityOptionalStringCell('')).toBe(TRADING_BALANCE_UNAVAILABLE_MARK);
  });

  it('returns value when present', () => {
    expect(formatActivityOptionalStringCell('0.01')).toBe('0.01');
  });
});
