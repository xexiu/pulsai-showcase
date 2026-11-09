// @vitest-environment node
/**
 * Constants tests — backtest defaults, training statuses, time & polling (split from constants.test.ts).
 */

import { describe, expect, it } from 'vitest';

import { BACKTEST_DEFAULTS, POLL_INTERVALS, TIME_MS, TRAINING_STATUSES } from '@/utils/constants';

describe('BACKTEST_DEFAULTS', () => {
  it('includes MIN_NET_PCT aligned with BE DEFAULT_BACKTEST_MIN_NET_PCT', () => {
    expect(BACKTEST_DEFAULTS.MIN_NET_PCT).toBe(0);
  });

  it('includes MAX_SL_PCT null for no ATR cap (BE DEFAULT_BACKTEST_MAX_SL_PCT)', () => {
    expect(BACKTEST_DEFAULTS.MAX_SL_PCT).toBeNull();
  });
});

describe('TRAINING_STATUSES', () => {
  describe('values', () => {
    it('has PENDING status', () => {
      expect(TRAINING_STATUSES.PENDING).toBe('pending');
    });

    it('has VALIDATING status', () => {
      expect(TRAINING_STATUSES.VALIDATING).toBe('validating');
    });

    it('has RUNNING status', () => {
      expect(TRAINING_STATUSES.RUNNING).toBe('running');
    });

    it('has PAUSED status', () => {
      expect(TRAINING_STATUSES.PAUSED).toBe('paused');
    });

    it('has COMPLETED status', () => {
      expect(TRAINING_STATUSES.COMPLETED).toBe('completed');
    });

    it('has COMPLETED_NOT_PROMOTED status', () => {
      expect(TRAINING_STATUSES.COMPLETED_NOT_PROMOTED).toBe('completed_not_promoted');
    });

    it('has FAILED status', () => {
      expect(TRAINING_STATUSES.FAILED).toBe('failed');
    });

    it('has CANCELLED status', () => {
      expect(TRAINING_STATUSES.CANCELLED).toBe('cancelled');
    });
  });

  describe('completeness', () => {
    it('has all expected statuses', () => {
      const keys = Object.keys(TRAINING_STATUSES);

      expect(keys).toHaveLength(8);
      expect(keys).toContain('PENDING');
      expect(keys).toContain('VALIDATING');
      expect(keys).toContain('RUNNING');
      expect(keys).toContain('PAUSED');
      expect(keys).toContain('COMPLETED');
      expect(keys).toContain('COMPLETED_NOT_PROMOTED');
      expect(keys).toContain('FAILED');
      expect(keys).toContain('CANCELLED');
    });
  });
});

describe('TIME_MS', () => {
  describe('values', () => {
    it('has correct SECOND value', () => {
      expect(TIME_MS.SECOND).toBe(1000);
    });

    it('has correct MINUTE value', () => {
      expect(TIME_MS.MINUTE).toBe(60000);
    });

    it('has correct HOUR value', () => {
      expect(TIME_MS.HOUR).toBe(3600000);
    });

    it('has correct DAY value', () => {
      expect(TIME_MS.DAY).toBe(86400000);
    });
  });

  describe('mathematical relationships', () => {
    it('MINUTE equals 60 SECONDS', () => {
      expect(TIME_MS.MINUTE).toBe(TIME_MS.SECOND * 60);
    });

    it('HOUR equals 60 MINUTES', () => {
      expect(TIME_MS.HOUR).toBe(TIME_MS.MINUTE * 60);
    });

    it('DAY equals 24 HOURS', () => {
      expect(TIME_MS.DAY).toBe(TIME_MS.HOUR * 24);
    });
  });
});

describe('POLL_INTERVALS', () => {
  describe('values', () => {
    it('has REALTIME interval (2s)', () => {
      expect(POLL_INTERVALS.REALTIME).toBe(2000);
    });

    it('has STANDARD interval (30s)', () => {
      expect(POLL_INTERVALS.STANDARD).toBe(30000);
    });

    it('has SLOW interval (60s)', () => {
      expect(POLL_INTERVALS.SLOW).toBe(60000);
    });

    it('has RECONNECT interval (3s)', () => {
      expect(POLL_INTERVALS.RECONNECT).toBe(3000);
    });

    it('has FETCH_TIMEOUT interval (10s)', () => {
      expect(POLL_INTERVALS.FETCH_TIMEOUT).toBe(10000);
    });
  });

  describe('reasonable ordering', () => {
    it('REALTIME is faster than STANDARD', () => {
      expect(POLL_INTERVALS.REALTIME).toBeLessThan(POLL_INTERVALS.STANDARD);
    });

    it('STANDARD is faster than SLOW', () => {
      expect(POLL_INTERVALS.STANDARD).toBeLessThan(POLL_INTERVALS.SLOW);
    });
  });
});
