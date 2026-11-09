// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { SIGNAL_ACTIONS } from '@/utils/constants';
import { buildMlSignalMarkerGlyphText } from '@/utils/constants/chart-ml-signal-marker-glyphs';
import {
  confidenceToMlSignalGlyphTier,
  confidenceToOpacity,
  ML_SIGNAL_LWC_GLYPH_ONLY_SIZE,
  resolveMlSignalMarkerVisual,
} from '@/utils/signal-marker-confidence-visual';

describe('ML signal LWC markers — triangle only (no backing circle)', () => {
  it('resolveMlSignalMarkerVisual always uses glyph-only LWC size 0', () => {
    expect(resolveMlSignalMarkerVisual(0).lwcSize).toBe(ML_SIGNAL_LWC_GLYPH_ONLY_SIZE);
    expect(resolveMlSignalMarkerVisual(100).lwcSize).toBe(ML_SIGNAL_LWC_GLYPH_ONLY_SIZE);
    expect(resolveMlSignalMarkerVisual(undefined).lwcSize).toBe(ML_SIGNAL_LWC_GLYPH_ONLY_SIZE);
  });

  it('still maps opacity from confidence', () => {
    const visual = resolveMlSignalMarkerVisual(80);

    expect(visual.opacity).toBe(confidenceToOpacity(80));
  });
});

describe('confidenceToMlSignalGlyphTier', () => {
  it('returns small for low confidence', () => {
    expect(confidenceToMlSignalGlyphTier(10)).toBe('small');
  });

  it('returns medium for mid confidence', () => {
    expect(confidenceToMlSignalGlyphTier(50)).toBe('medium');
  });

  it('returns large for high confidence', () => {
    expect(confidenceToMlSignalGlyphTier(90)).toBe('large');
  });
});

describe('buildMlSignalMarkerGlyphText — confidence-sized triangles', () => {
  it('BUY low confidence uses smallest up triangle glyph', () => {
    expect(buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.BUY, { confidencePercent: 10 })).toBe('▵');
  });

  it('BUY high confidence uses largest up triangle glyph', () => {
    expect(buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.BUY, { confidencePercent: 95 })).toBe('▲');
  });

  it('SELL high confidence uses largest down triangle glyph', () => {
    expect(buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.SELL, { confidencePercent: 95 })).toBe('▼');
  });

  it('higher-TF suffix preserves confidence-sized glyph', () => {
    expect(
      buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.BUY, {
        confidencePercent: 95,
        suffix: '4h',
      })
    ).toBe('▲ 4h');
  });
});
