// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { TRADING_OVERVIEW_TAB_KEYS, resolveTradeOverviewTabKeys } from '@/utils/constants/trading';

describe('resolveTradeOverviewTabKeys', () => {
  it('returns trade right-column tab keys (chart renders above the tab bar when enabled)', () => {
    expect(resolveTradeOverviewTabKeys()).toEqual([...TRADING_OVERVIEW_TAB_KEYS]);
  });
});
