// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { formatActivityLeverageDisplay } from '@/utils/trading/format-activity-leverage-display';

describe('formatActivityLeverageDisplay', () => {
  it('returns null for spot or missing swap leverage', () => {
    expect(formatActivityLeverageDisplay('spot', 10)).toBeNull();
    expect(formatActivityLeverageDisplay('swap', null)).toBeNull();
    expect(formatActivityLeverageDisplay('swap', undefined)).toBeNull();
  });

  it('formats swap leverage as Nx', () => {
    expect(formatActivityLeverageDisplay('swap', 10)).toBe('10x');
    expect(formatActivityLeverageDisplay('swap', 3.5)).toBe('3.5x');
  });
});
