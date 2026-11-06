// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  confidenceToMlSignalGlyphTier,
  confidenceToOpacity,
  confidenceToPlotlyEntryMarkerSize,
  ML_SIGNAL_LWC_GLYPH_ONLY_SIZE,
  resolveMlSignalMarkerVisual,
  SIGNAL_DOT_DEFAULT_OPACITY,
  SIGNAL_DOT_MAX_OPACITY,
  SIGNAL_DOT_MIN_OPACITY,
  SIGNAL_ENTRY_MARKER_DEFAULT_SIZE,
  SIGNAL_ENTRY_MARKER_MAX_SIZE,
  SIGNAL_ENTRY_MARKER_MIN_SIZE,
} from '@/utils/signal-marker-confidence-visual';

describe('confidenceToOpacity', () => {
  it('returns MIN_OPACITY for confidence 0', () => {
    expect(confidenceToOpacity(0)).toBeCloseTo(SIGNAL_DOT_MIN_OPACITY);
  });

  it('returns MAX_OPACITY for confidence 100', () => {
    expect(confidenceToOpacity(100)).toBeCloseTo(SIGNAL_DOT_MAX_OPACITY);
  });

  it('returns DEFAULT_OPACITY when confidence is undefined', () => {
    expect(confidenceToOpacity(undefined)).toBeCloseTo(SIGNAL_DOT_DEFAULT_OPACITY);
  });
});

describe('confidenceToPlotlyEntryMarkerSize', () => {
  it('returns MIN_SIZE for confidence 0', () => {
    expect(confidenceToPlotlyEntryMarkerSize(0)).toBe(SIGNAL_ENTRY_MARKER_MIN_SIZE);
  });

  it('returns MAX_SIZE for confidence 100', () => {
    expect(confidenceToPlotlyEntryMarkerSize(100)).toBe(SIGNAL_ENTRY_MARKER_MAX_SIZE);
  });

  it('returns DEFAULT_SIZE for undefined confidence', () => {
    expect(confidenceToPlotlyEntryMarkerSize(undefined)).toBe(SIGNAL_ENTRY_MARKER_DEFAULT_SIZE);
  });
});

describe('confidenceToMlSignalGlyphTier', () => {
  it('returns large when confidence is missing', () => {
    expect(confidenceToMlSignalGlyphTier(undefined)).toBe('large');
  });

  it('returns small, medium, large by confidence band', () => {
    expect(confidenceToMlSignalGlyphTier(10)).toBe('small');
    expect(confidenceToMlSignalGlyphTier(50)).toBe('medium');
    expect(confidenceToMlSignalGlyphTier(90)).toBe('large');
  });
});

describe('resolveMlSignalMarkerVisual', () => {
  it('always keeps LWC size at 0 (triangle glyph only)', () => {
    expect(resolveMlSignalMarkerVisual(0).lwcSize).toBe(ML_SIGNAL_LWC_GLYPH_ONLY_SIZE);
    expect(resolveMlSignalMarkerVisual(100).lwcSize).toBe(ML_SIGNAL_LWC_GLYPH_ONLY_SIZE);
  });

  it('returns opacity and glyph tier from confidence', () => {
    const visual = resolveMlSignalMarkerVisual(80);

    expect(visual.opacity).toBe(confidenceToOpacity(80));
    expect(visual.glyphTier).toBe('large');
  });
});
