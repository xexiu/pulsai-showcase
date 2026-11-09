// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  confidenceToOpacity,
  SIGNAL_DOT_DEFAULT_OPACITY,
  SIGNAL_DOT_MAX_OPACITY,
  SIGNAL_DOT_MIN_OPACITY,
} from '@/utils/signal-marker-confidence-visual';

describe('confidenceToOpacity', () => {
  it('returns MIN_OPACITY for confidence 0', () => {
    expect(confidenceToOpacity(0)).toBeCloseTo(SIGNAL_DOT_MIN_OPACITY);
  });

  it('returns MAX_OPACITY for confidence 100', () => {
    expect(confidenceToOpacity(100)).toBeCloseTo(SIGNAL_DOT_MAX_OPACITY);
  });

  it('returns midpoint opacity for confidence 50', () => {
    const expected =
      SIGNAL_DOT_MIN_OPACITY + 0.5 * (SIGNAL_DOT_MAX_OPACITY - SIGNAL_DOT_MIN_OPACITY);

    expect(confidenceToOpacity(50)).toBeCloseTo(expected);
  });

  it('returns DEFAULT_OPACITY when confidence is undefined', () => {
    expect(confidenceToOpacity(undefined)).toBeCloseTo(SIGNAL_DOT_DEFAULT_OPACITY);
  });

  it('returns DEFAULT_OPACITY when confidence is NaN', () => {
    expect(confidenceToOpacity(NaN)).toBeCloseTo(SIGNAL_DOT_DEFAULT_OPACITY);
  });

  it('clamps negative confidence to MIN_OPACITY', () => {
    expect(confidenceToOpacity(-10)).toBeCloseTo(SIGNAL_DOT_MIN_OPACITY);
  });

  it('clamps confidence above 100 to MAX_OPACITY', () => {
    expect(confidenceToOpacity(150)).toBeCloseTo(SIGNAL_DOT_MAX_OPACITY);
  });

  it('is monotonically increasing between 0 and 100', () => {
    const o25 = confidenceToOpacity(25);
    const o50 = confidenceToOpacity(50);
    const o75 = confidenceToOpacity(75);

    expect(o25).toBeLessThan(o50);
    expect(o50).toBeLessThan(o75);
  });
});
