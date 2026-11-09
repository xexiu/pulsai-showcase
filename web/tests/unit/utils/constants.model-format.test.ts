// @vitest-environment node
/**
 * Constants tests — model display helpers (split from constants.test.ts).
 */

import { describe, expect, it } from 'vitest';

import {
  formatModelTypeForDisplay,
  formatModelTypeToArchitectureName,
  sortModelsByVersionDesc,
} from '@/utils/constants';

describe('formatModelTypeForDisplay', () => {
  it('returns 3-class for xgboost_3class', () => {
    expect(formatModelTypeForDisplay('xgboost_3class')).toBe('3-class');
  });

  it('returns 2-class BUY for xgboost_2class_buy', () => {
    expect(formatModelTypeForDisplay('xgboost_2class_buy')).toBe('2-class BUY');
  });

  it('returns 2-class SELL for xgboost_2class_sell', () => {
    expect(formatModelTypeForDisplay('xgboost_2class_sell')).toBe('2-class SELL');
  });

  it('returns 3-class for null or undefined', () => {
    expect(formatModelTypeForDisplay(null)).toBe('3-class');
    expect(formatModelTypeForDisplay(undefined)).toBe('3-class');
  });

  it('is case insensitive', () => {
    expect(formatModelTypeForDisplay('XGBOOST_2CLASS_BUY')).toBe('2-class BUY');
  });

  it('returns architecture Regression for tree regressors', () => {
    expect(formatModelTypeForDisplay('xgboost_regression')).toBe('XGBoost Regression');
    expect(formatModelTypeForDisplay('lightgbm_regression')).toBe('LightGBM Regression');
  });
});

describe('formatModelTypeToArchitectureName', () => {
  it('returns XGBoost for xgboost_3class', () => {
    expect(formatModelTypeToArchitectureName('xgboost_3class')).toBe('XGBoost');
  });

  it('returns LSTM for lstm_3class (future)', () => {
    expect(formatModelTypeToArchitectureName('lstm_3class')).toBe('LSTM');
  });

  it('returns GRU for gru_3class (future)', () => {
    expect(formatModelTypeToArchitectureName('gru_3class')).toBe('GRU');
  });

  it('returns Random Forest for rf_3class', () => {
    expect(formatModelTypeToArchitectureName('rf_3class')).toBe('Random Forest');
  });

  it('returns XGBoost for null/undefined (default)', () => {
    expect(formatModelTypeToArchitectureName(null)).toBe('XGBoost');
    expect(formatModelTypeToArchitectureName(undefined)).toBe('XGBoost');
  });

  it('capitalizes unknown prefix as fallback', () => {
    expect(formatModelTypeToArchitectureName('custom_3class')).toBe('Custom');
  });
});

describe('sortModelsByVersionDesc', () => {
  it('returns newest version first', () => {
    const models = [
      { version: 1, symbol: 'BTC/USDT' },
      { version: 3, symbol: 'BTC/USDT' },
      { version: 2, symbol: 'BTC/USDT' },
    ];
    const sorted = sortModelsByVersionDesc(models);

    expect(sorted.map((m) => m.version)).toEqual([3, 2, 1]);
  });

  it('does not mutate the input array', () => {
    const models = [
      { version: 1, symbol: 'BTC/USDT' },
      { version: 2, symbol: 'BTC/USDT' },
    ];
    const original = [...models];

    sortModelsByVersionDesc(models);

    expect(models).toEqual(original);
  });

  it('returns an empty array unchanged', () => {
    expect(sortModelsByVersionDesc([])).toEqual([]);
  });

  it('handles a single-element array', () => {
    const models = [{ version: 5, symbol: 'ETH/USDT' }];

    expect(sortModelsByVersionDesc(models)).toEqual(models);
  });

  it('preserves all model fields while sorting', () => {
    const models = [
      { version: 1, symbol: 'ETH/USDT', is_production: false },
      { version: 2, symbol: 'BTC/USDT', is_production: true },
    ];
    const sorted = sortModelsByVersionDesc(models);

    expect(sorted[0]).toEqual({ version: 2, symbol: 'BTC/USDT', is_production: true });
    expect(sorted[1]).toEqual({ version: 1, symbol: 'ETH/USDT', is_production: false });
  });
});
