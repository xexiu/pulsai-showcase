/**
 * ML signal marker glyphs for lightweight-charts (live chart).
 *
 * LWC has no filled triangle shape — only arrowUp/arrowDown (stem + head). SoT workaround:
 * ▲/▼ glyphs in marker `text` with `size: 0` so LWC skips `drawShape` (no circles).
 * Confidence scales the **glyph tier** (▵/▴/▲) and opacity, not LWC `size`.
 *
 * @see apps/web/src/utils/plotly-chart-helpers/entry-traces.ts (backtest triangle-up/down)
 */

import { SIGNAL_ACTIONS } from '@/utils/constants';
import {
  confidenceToMlSignalGlyphTier,
  ML_SIGNAL_LWC_GLYPH_ONLY_SIZE,
  type MlSignalGlyphSizeTier,
} from '@/utils/signal-marker-confidence-visual';

/** Filled-triangle glyphs by confidence tier (BUY up / SELL down). */
export const CHART_ML_SIGNAL_MARKER_GLYPH_BY_TIER = {
  [SIGNAL_ACTIONS.BUY]: {
    small: '▵',
    medium: '▴',
    large: '▲',
  },
  [SIGNAL_ACTIONS.SELL]: {
    small: '▿',
    medium: '▾',
    large: '▼',
  },
} as const satisfies Record<
  typeof SIGNAL_ACTIONS.BUY | typeof SIGNAL_ACTIONS.SELL,
  Record<MlSignalGlyphSizeTier, string>
>;

/** Legacy default glyph (large tier) for callers without confidence. */
export const CHART_ML_SIGNAL_MARKER_GLYPH = {
  [SIGNAL_ACTIONS.BUY]: CHART_ML_SIGNAL_MARKER_GLYPH_BY_TIER[SIGNAL_ACTIONS.BUY].large,
  [SIGNAL_ACTIONS.SELL]: CHART_ML_SIGNAL_MARKER_GLYPH_BY_TIER[SIGNAL_ACTIONS.SELL].large,
} as const;

/** Placeholder shape; size 0 skips LWC drawShape. */
export const CHART_ML_SIGNAL_MARKER_LWC_SHAPE = 'circle' as const;

/** ML + RSI glyph-only markers: size 0 → no backing circle. */
export const CHART_MARKER_GLYPH_ONLY_LWC_SIZE = ML_SIGNAL_LWC_GLYPH_ONLY_SIZE;

type BuySellAction = typeof SIGNAL_ACTIONS.BUY | typeof SIGNAL_ACTIONS.SELL;

export type BuildMlSignalMarkerGlyphTextOptions = {
  suffix?: string;
  confidencePercent?: number;
  glyphTier?: MlSignalGlyphSizeTier;
};

function resolveGlyphTier(options?: BuildMlSignalMarkerGlyphTextOptions): MlSignalGlyphSizeTier {
  if (options?.glyphTier != null) {
    return options.glyphTier;
  }

  return confidenceToMlSignalGlyphTier(options?.confidencePercent);
}

/**
 * Marker text for ML signals: confidence-sized ▲/▼, optionally suffixed (e.g. ``▲ 4h``).
 */
export function buildMlSignalMarkerGlyphText(
  action: BuySellAction,
  options?: BuildMlSignalMarkerGlyphTextOptions | string
): string {
  const normalized: BuildMlSignalMarkerGlyphTextOptions =
    typeof options === 'string' ? { suffix: options } : (options ?? {});

  const tier = resolveGlyphTier(normalized);
  const glyph = CHART_ML_SIGNAL_MARKER_GLYPH_BY_TIER[action][tier];
  const { suffix } = normalized;

  if (!suffix || suffix.length === 0) {
    return glyph;
  }

  return `${glyph} ${suffix}`;
}
