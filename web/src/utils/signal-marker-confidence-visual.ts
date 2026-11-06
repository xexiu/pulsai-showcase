/**
 * SoT: ML signal marker visual encoding from confidence (0–100%).
 *
 * - Plotly backtest: triangle marker size (px) + opacity.
 * - LWC live chart: triangle **glyph** tier + opacity only (`size` stays 0 — LWC draws
 *   a circle when size > 0; see `chart-ml-signal-marker-glyphs.ts`).
 */

/** LWC `size` for ML markers — must stay 0 so only text glyph renders (no circle). */
export const ML_SIGNAL_LWC_GLYPH_ONLY_SIZE = 0;

/** Low / mid confidence boundary for glyph tier (exclusive upper bound for small). */
const SIGNAL_ML_GLYPH_TIER_SMALL_MAX_PERCENT = 33;
/** Mid / high confidence boundary for glyph tier (exclusive upper bound for medium). */
const SIGNAL_ML_GLYPH_TIER_MEDIUM_MAX_PERCENT = 67;

export const SIGNAL_DOT_MIN_OPACITY = 0.2;
export const SIGNAL_DOT_MAX_OPACITY = 0.95;
export const SIGNAL_DOT_DEFAULT_OPACITY = 0.7;

/** Plotly BUY/SELL entry triangle marker size (px). */
export const SIGNAL_ENTRY_MARKER_MIN_SIZE = 9;
export const SIGNAL_ENTRY_MARKER_MAX_SIZE = 15;
export const SIGNAL_ENTRY_MARKER_DEFAULT_SIZE = 12;

export type MlSignalGlyphSizeTier = 'small' | 'medium' | 'large';

function mapConfidencePercentToRange(
  confidence: number | undefined,
  min: number,
  max: number,
  defaultValue: number
): number {
  if (confidence == null || !Number.isFinite(confidence)) {
    return defaultValue;
  }

  const clamped = Math.max(0, Math.min(100, confidence));

  return min + (clamped / 100) * (max - min);
}

/** Linear map: confidence (0–100%) → marker opacity. */
export function confidenceToOpacity(confidence: number | undefined): number {
  return mapConfidencePercentToRange(
    confidence,
    SIGNAL_DOT_MIN_OPACITY,
    SIGNAL_DOT_MAX_OPACITY,
    SIGNAL_DOT_DEFAULT_OPACITY
  );
}

/** Linear map: confidence (0–100%) → Plotly entry triangle size (px). */
export function confidenceToPlotlyEntryMarkerSize(confidence: number | undefined): number {
  return Math.round(
    mapConfidencePercentToRange(
      confidence,
      SIGNAL_ENTRY_MARKER_MIN_SIZE,
      SIGNAL_ENTRY_MARKER_MAX_SIZE,
      SIGNAL_ENTRY_MARKER_DEFAULT_SIZE
    )
  );
}

/** Map confidence to triangle glyph size tier (LWC text glyph — no backing shape). */
export function confidenceToMlSignalGlyphTier(
  confidence: number | undefined
): MlSignalGlyphSizeTier {
  if (confidence == null || !Number.isFinite(confidence)) {
    return 'large';
  }

  const percent = Math.max(0, Math.min(100, confidence));

  if (percent < SIGNAL_ML_GLYPH_TIER_SMALL_MAX_PERCENT) {
    return 'small';
  }

  if (percent < SIGNAL_ML_GLYPH_TIER_MEDIUM_MAX_PERCENT) {
    return 'medium';
  }

  return 'large';
}

/** Opacity + glyph-only LWC size for one ML signal marker (0–100% confidence). */
export function resolveMlSignalMarkerVisual(confidencePercent: number | undefined): {
  opacity: number;
  lwcSize: number;
  glyphTier: MlSignalGlyphSizeTier;
} {
  return {
    opacity: confidenceToOpacity(confidencePercent),
    lwcSize: ML_SIGNAL_LWC_GLYPH_ONLY_SIZE,
    glyphTier: confidenceToMlSignalGlyphTier(confidencePercent),
  };
}
