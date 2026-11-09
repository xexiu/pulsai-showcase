// @vitest-environment node
/**
 * Paper trading constant helpers — getTradingModeBadgeVariant, getModeButtonClass, getSideButtonClass.
 */

import { describe, expect, it } from 'vitest';

import {
  getModeButtonClass,
  getSideButtonClass,
  getTradingModeBadgeVariant,
} from '@/utils/constants/trading';

describe('getTradingModeBadgeVariant', () => {
  it('returns info for paper', () => {
    expect(getTradingModeBadgeVariant('paper')).toBe('info');
  });

  it('returns warning for demo', () => {
    expect(getTradingModeBadgeVariant('demo')).toBe('warning');
  });

  it('returns success for live (real trading; green badge)', () => {
    expect(getTradingModeBadgeVariant('live')).toBe('success');
  });
});

describe('getModeButtonClass', () => {
  it('returns primary classes when selected', () => {
    expect(getModeButtonClass(true)).toContain('border-primary');
  });

  it('returns muted classes when not selected', () => {
    expect(getModeButtonClass(false)).toContain('text-muted-foreground');
  });
});

describe('getSideButtonClass', () => {
  it('returns green for active buy', () => {
    expect(getSideButtonClass(true, 'buy')).toContain('bg-green-600');
  });

  it('returns red for active sell', () => {
    expect(getSideButtonClass(true, 'sell')).toContain('bg-red-600');
  });

  it('returns border class for inactive', () => {
    expect(getSideButtonClass(false, 'buy')).toContain('border-border');
  });
});
