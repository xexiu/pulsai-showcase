// @vitest-environment node
/**
 * Constants tests — signal actions & exit strategies (split from constants.test.ts).
 */

import { describe, expect, it } from 'vitest';

import { EXIT_STRATEGIES, SIGNAL_ACTIONS } from '@/utils/constants';

describe('SIGNAL_ACTIONS', () => {
  describe('values', () => {
    it('has BUY action', () => {
      expect(SIGNAL_ACTIONS.BUY).toBe('BUY');
    });

    it('has SELL action', () => {
      expect(SIGNAL_ACTIONS.SELL).toBe('SELL');
    });

    it('has HOLD action', () => {
      expect(SIGNAL_ACTIONS.HOLD).toBe('HOLD');
    });
  });

  describe('type safety', () => {
    it('has all expected keys', () => {
      const keys = Object.keys(SIGNAL_ACTIONS);

      expect(keys).toContain('BUY');
      expect(keys).toContain('SELL');
      expect(keys).toContain('HOLD');
      expect(keys).toHaveLength(3);
    });
  });
});

describe('EXIT_STRATEGIES', () => {
  describe('values', () => {
    it('has FIXED_HOLDING strategy', () => {
      expect(EXIT_STRATEGIES.FIXED_HOLDING).toBe('fixed_holding');
    });

    it('has RAW_SIGNAL strategy', () => {
      expect(EXIT_STRATEGIES.RAW_SIGNAL).toBe('raw_signal');
    });

    it('has FIXED_TPSL strategy', () => {
      expect(EXIT_STRATEGIES.FIXED_TPSL).toBe('fixed_tpsl');
    });

    it('has RISK_REWARD strategy', () => {
      expect(EXIT_STRATEGIES.RISK_REWARD).toBe('risk_reward');
    });

    it('has TRAILING_STOP strategy', () => {
      expect(EXIT_STRATEGIES.TRAILING_STOP).toBe('trailing_stop');
    });

    it('has ATR_BASED strategy', () => {
      expect(EXIT_STRATEGIES.ATR_BASED).toBe('atr_based');
    });

    it('has DYNAMIC_TPSL strategy', () => {
      expect(EXIT_STRATEGIES.DYNAMIC_TPSL).toBe('dynamic_tpsl');
    });
  });

  describe('completeness', () => {
    it('has all expected strategies', () => {
      const keys = Object.keys(EXIT_STRATEGIES);

      expect(keys).toHaveLength(9);
      expect(keys).toContain('FIXED_HOLDING');
      expect(keys).toContain('RAW_SIGNAL');
      expect(keys).toContain('FIXED_TPSL');
      expect(keys).toContain('RISK_REWARD');
      expect(keys).toContain('TRAILING_STOP');
      expect(keys).toContain('ATR_BASED');
      expect(keys).toContain('DYNAMIC_TPSL');
      expect(keys).toContain('PREDICTED_REGRESSOR');
      expect(keys).toContain('MIN_PROFIT_AFTER_FEES');
    });
  });
});
