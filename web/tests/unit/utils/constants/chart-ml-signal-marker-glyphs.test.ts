// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { SIGNAL_ACTIONS } from '@/utils/constants';
import {
  buildMlSignalMarkerGlyphText,
  CHART_ML_SIGNAL_MARKER_GLYPH,
  CHART_ML_SIGNAL_MARKER_GLYPH_BY_TIER,
  CHART_MARKER_GLYPH_ONLY_LWC_SIZE,
  CHART_ML_SIGNAL_MARKER_LWC_SHAPE,
} from '@/utils/constants/chart-ml-signal-marker-glyphs';

describe('chart-ml-signal-marker-glyphs', () => {
  it('uses filled triangle unicode glyphs for buy and sell (large tier)', () => {
    expect(CHART_ML_SIGNAL_MARKER_GLYPH[SIGNAL_ACTIONS.BUY]).toBe('▲');
    expect(CHART_ML_SIGNAL_MARKER_GLYPH[SIGNAL_ACTIONS.SELL]).toBe('▼');
    expect(CHART_ML_SIGNAL_MARKER_GLYPH_BY_TIER[SIGNAL_ACTIONS.BUY].small).toBe('▵');
  });

  it('uses LWC size 0 so only the text glyph is drawn', () => {
    expect(CHART_MARKER_GLYPH_ONLY_LWC_SIZE).toBe(0);
    expect(CHART_ML_SIGNAL_MARKER_LWC_SHAPE).toBe('circle');
  });

  it('buildMlSignalMarkerGlyphText returns confidence-sized glyph or glyph + suffix', () => {
    expect(buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.BUY)).toBe('▲');
    expect(buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.SELL, { confidencePercent: 10 })).toBe('▿');
    expect(buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.BUY, '4h')).toBe('▲ 4h');
    expect(
      buildMlSignalMarkerGlyphText(SIGNAL_ACTIONS.BUY, { confidencePercent: 95, suffix: '4h' })
    ).toBe('▲ 4h');
  });
});
