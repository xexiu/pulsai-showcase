// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  filterOrderRowsToOpenResting,
  isOpenRestingOrderStatus,
} from '@/utils/trading/is-open-resting-order-status';

describe('isOpenRestingOrderStatus', () => {
  it('treats demo pending and CCXT open / new / partial as resting', () => {
    expect(isOpenRestingOrderStatus('pending')).toBe(true);
    expect(isOpenRestingOrderStatus('PENDING')).toBe(true);
    expect(isOpenRestingOrderStatus('open')).toBe(true);
    expect(isOpenRestingOrderStatus('new')).toBe(true);
    expect(isOpenRestingOrderStatus('partially_filled')).toBe(true);
  });

  it('treats terminal / closed lifecycle as not resting', () => {
    expect(isOpenRestingOrderStatus('filled')).toBe(false);
    expect(isOpenRestingOrderStatus('cancelled')).toBe(false);
    expect(isOpenRestingOrderStatus('failed')).toBe(false);
    expect(isOpenRestingOrderStatus('fill_unknown')).toBe(false);
    expect(isOpenRestingOrderStatus('closed')).toBe(false);
    expect(isOpenRestingOrderStatus('canceled')).toBe(false);
  });
});

describe('filterOrderRowsToOpenResting', () => {
  it('keeps only working rows (demo + paper/live shapes)', () => {
    const rows = [
      { status: 'pending', id: 'a' },
      { status: 'partially_filled', id: 'b' },
      { status: 'filled', id: 'c' },
      { status: 'cancelled', id: 'd' },
    ];

    expect(filterOrderRowsToOpenResting(rows)).toEqual([
      { status: 'pending', id: 'a' },
      { status: 'partially_filled', id: 'b' },
    ]);
  });
});
