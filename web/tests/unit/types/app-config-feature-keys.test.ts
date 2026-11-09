// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  FEATURES_CONFIG_KEYS,
  FEATURES_CONFIG_KEY_FUTURES_TRADING_UI,
  type FeaturesConfig,
  type FeaturesConfigFuturesTradingUiKey,
} from '@/types/app-config';
import {
  FEATURES_CONFIG_KEYS as barrelKeys,
  FEATURES_CONFIG_KEY_FUTURES_TRADING_UI as barrelFuturesKey,
} from '@/types/tradingBarrel';

describe('FEATURES_CONFIG_KEYS', () => {
  it('matches trading barrel re-export', () => {
    expect(barrelKeys).toBe(FEATURES_CONFIG_KEYS);
  });

  it('maps each FeaturesConfig field to its JSON wire key', () => {
    const mapping: { [K in keyof FeaturesConfig]: K } = {
      backtest: FEATURES_CONFIG_KEYS.backtest,
      live_trading: FEATURES_CONFIG_KEYS.live_trading,
      visual_patterns: FEATURES_CONFIG_KEYS.visual_patterns,
      futures_paper_trading: FEATURES_CONFIG_KEYS.futures_paper_trading,
      inference_compare: FEATURES_CONFIG_KEYS.inference_compare,
    };

    expect(mapping.futures_paper_trading).toBe(FEATURES_CONFIG_KEY_FUTURES_TRADING_UI);
    const values = Object.values(FEATURES_CONFIG_KEYS);

    expect(new Set(values).size).toBe(values.length);
  });
});

describe('FEATURES_CONFIG_KEY_FUTURES_TRADING_UI', () => {
  it('is the wire key for futures Spot/Futures UI gate on public config features', () => {
    expect(FEATURES_CONFIG_KEY_FUTURES_TRADING_UI).toBe('futures_paper_trading');
  });

  it('matches trading barrel re-export (single SoT for trading consumers)', () => {
    expect(barrelFuturesKey).toBe(FEATURES_CONFIG_KEY_FUTURES_TRADING_UI);
  });

  it('FeaturesConfigFuturesTradingUiKey aligns with FEATURES_CONFIG_KEY_FUTURES_TRADING_UI', () => {
    const k: FeaturesConfigFuturesTradingUiKey = FEATURES_CONFIG_KEY_FUTURES_TRADING_UI;

    expect(k).toBe('futures_paper_trading');
  });

  it('indexes a minimal FeaturesConfig pick (wire parity with GET /config/public)', () => {
    const row: Pick<FeaturesConfig, FeaturesConfigFuturesTradingUiKey> = {
      futures_paper_trading: true,
    };

    expect(row[FEATURES_CONFIG_KEY_FUTURES_TRADING_UI]).toBe(true);
  });
});
