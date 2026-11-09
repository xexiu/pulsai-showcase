// @vitest-environment node
/**
 * Barrel re-export — key constants remain reachable via `@/utils/constants/trading`.
 */

import { describe, expect, it } from 'vitest';

import { MARKET_TYPE, TRADING_MODE } from '@/utils/constants/trading';

describe('trading barrel', () => {
  it('re-exports MARKET_TYPE.SPOT', () => {
    expect(MARKET_TYPE.SPOT).toBe('spot');
  });

  it('re-exports TRADING_MODE.DEMO', () => {
    expect(TRADING_MODE.DEMO).toBe('demo');
  });
});
