// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  FEATURES_CONFIG_KEYS as keysFromAppConfig,
  FEATURES_CONFIG_KEY_FUTURES_TRADING_UI as fromAppConfig,
} from '@/types/app-config';
import {
  FEATURES_CONFIG_KEYS as keysFromPaperTradingBarrel,
  FEATURES_CONFIG_KEY_FUTURES_TRADING_UI as fromPaperTradingBarrel,
} from '@/types/tradingBarrel';

describe('@/types/tradingBarrel barrel', () => {
  it('re-exports FEATURES_CONFIG_KEY_FUTURES_TRADING_UI same as app-config SoT', () => {
    expect(fromPaperTradingBarrel).toBe(fromAppConfig);
    expect(fromPaperTradingBarrel).toBe('futures_paper_trading');
  });

  it('re-exports FEATURES_CONFIG_KEYS same object as app-config SoT', () => {
    expect(keysFromPaperTradingBarrel).toBe(keysFromAppConfig);
  });
});
