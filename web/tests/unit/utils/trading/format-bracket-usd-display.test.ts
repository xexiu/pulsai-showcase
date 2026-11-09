// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { formatBracketUsdDisplay } from '@/utils/trading/format-bracket-usd-display';

describe('formatBracketUsdDisplay', () => {
  it('returns dash for nullish or empty', () => {
    expect(formatBracketUsdDisplay(null)).toBe('-');
    expect(formatBracketUsdDisplay(undefined)).toBe('-');
    expect(formatBracketUsdDisplay('')).toBe('-');
    expect(formatBracketUsdDisplay('   ')).toBe('-');
  });

  it('formats numeric strings as USD', () => {
    expect(formatBracketUsdDisplay('75568.2246')).toMatch(/\$75/);
  });
});
