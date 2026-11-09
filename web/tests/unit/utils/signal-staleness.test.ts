// @vitest-environment node
// =============================================================================
// signal-staleness — pure util tests
// =============================================================================
//
// Behavior covered:
// - null / undefined signal → not stale (defensive: caller can show default copy)
// - missing timestamp → not stale
// - unknown timeframe → not stale (no threshold to apply)
// - fresh signal (age < 1.5 × tfMs) → not stale
// - boundary (age === 1.5 × tfMs) → not stale (strict >)
// - aged signal (age > 1.5 × tfMs) → stale
// - far-future timestamp (clock skew) → not stale
// =============================================================================

import { describe, expect, it } from 'vitest';

import {
  isSignalStale,
  SIGNAL_STALE_THRESHOLD_MULTIPLIER,
} from '@/utils/chart-time/signal-staleness';

const FIVE_MIN_MS = 5 * 60 * 1000;
const NOW = 1_780_000_000_000;

function makeSignal(
  timestampMs: number,
  timeframe = '5m'
): { timestamp: string; timeframe: string } {
  return { timestamp: new Date(timestampMs).toISOString(), timeframe };
}

describe('SIGNAL_STALE_THRESHOLD_MULTIPLIER', () => {
  it('is 1.5 (one-and-a-half timeframes is the cutoff)', () => {
    expect(SIGNAL_STALE_THRESHOLD_MULTIPLIER).toBe(1.5);
  });
});

describe('isSignalStale', () => {
  it('returns false for null signal (no signal → show default fresh copy)', () => {
    expect(isSignalStale(null, NOW)).toBe(false);
  });

  it('returns false for signal with missing timestamp', () => {
    expect(isSignalStale({ timestamp: '', timeframe: '5m' }, NOW)).toBe(false);
  });

  it('returns false for signal with unknown timeframe', () => {
    expect(isSignalStale(makeSignal(NOW - FIVE_MIN_MS, 'not-a-tf'), NOW)).toBe(false);
  });

  it('returns false when signal age is well under threshold (fresh)', () => {
    expect(isSignalStale(makeSignal(NOW - 60_000, '5m'), NOW)).toBe(false);
  });

  it('returns false at the exact boundary (age === 1.5 × tfMs)', () => {
    const boundaryAgeMs = FIVE_MIN_MS * SIGNAL_STALE_THRESHOLD_MULTIPLIER;

    expect(isSignalStale(makeSignal(NOW - boundaryAgeMs, '5m'), NOW)).toBe(false);
  });

  it('returns true when signal age exceeds threshold by 1 ms', () => {
    const overAgeMs = FIVE_MIN_MS * SIGNAL_STALE_THRESHOLD_MULTIPLIER + 1;

    expect(isSignalStale(makeSignal(NOW - overAgeMs, '5m'), NOW)).toBe(true);
  });

  it('returns true for very old signals (hours stale on a 5m timeframe)', () => {
    expect(isSignalStale(makeSignal(NOW - 3 * 60 * 60 * 1000, '5m'), NOW)).toBe(true);
  });

  it('returns false for future timestamps (negative age from clock skew)', () => {
    expect(isSignalStale(makeSignal(NOW + 60_000, '5m'), NOW)).toBe(false);
  });

  it('uses Date.now() when no clock is passed', () => {
    expect(isSignalStale(makeSignal(Date.now() - 1000, '5m'))).toBe(false);
  });
});
