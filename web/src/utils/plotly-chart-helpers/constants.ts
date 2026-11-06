export const RSI_OVERBOUGHT = 70;
export const RSI_OVERSOLD = 30;
export const SUBPLOT_HEIGHT = 0.15;
export const SUBPLOT_GAP = 0.2;

/**
 * Plotly stroke for single-mode equity / cumulative P&L curves (`SingleEquityCurve`).
 * Space-separated HSL inside `hsl()` — MUST match `globals.css` `--chart-equity-line`.
 */
export const PLOTLY_EQUITY_CURVE_LINE_LIGHT = 'hsl(271 91% 55%)' as const;
export const PLOTLY_EQUITY_CURVE_LINE_DARK = 'hsl(271 91% 65%)' as const;

/** Opacity for HOLD dots (lower than BUY/SELL so they don't dominate) */
export const PREDICTION_OPACITY_HOLD = 0.35;
/** Opacity for BUY/SELL dots (higher for visibility against dark chart backgrounds). */
export const PREDICTION_OPACITY_ACTIONABLE = 0.9;
/** Marker size for BUY/SELL/HOLD prediction dots. */
export const PREDICTION_MARKER_SIZE = 7;
/** Thin contrast stroke around prediction dots to improve visibility. */
export const PREDICTION_MARKER_STROKE_WIDTH = 1;

/**
 * Backtest CryptoBacktester: signal at candle i close → entry at candle i+1 open.
 * Unified Plotly hover stacks candlestick + entry markers, so users see this bar's
 * model line together with a triangle that executed the previous bar's decision.
 */
/** Shown on primary BUY/SELL scatter markers (backtest chart only). */
export const BACKTEST_SIGNAL_MARKER_EXECUTION_NOTE =
  "<i>Backtest: prior bar's signal, filled at this bar's open.</i>";

/**
 * BUY entry triangles sit slightly below `low`; SELL slightly above `high`.
 * Pad = max(range × this, close × ENTRY_SIGNAL_MARKER_PAD_MIN_FRACTION_OF_CLOSE).
 */
export const ENTRY_SIGNAL_MARKER_PAD_FRACTION_OF_RANGE = 0.12;
/** When the candle range is tiny (doji), still nudge markers outside the wick. */
export const ENTRY_SIGNAL_MARKER_PAD_MIN_FRACTION_OF_CLOSE = 0.00012;

// =============================================================================
// ML Feature Category Mapping (prefix-based, dynamic)
// =============================================================================

/**
 * Ordered categories for grouping ML model features in hover text.
 * Prefix-based: adding `rsi_28` automatically lands in "Momentum".
 * Features not matching any prefix fall into a catch-all "Other" bucket.
 */
export const FEATURE_CATEGORY_ORDER: ReadonlyArray<{
  label: string;
  prefixes: readonly string[];
}> = [
  { label: 'Momentum', prefixes: ['rsi_', 'macd', 'stoch_'] },
  { label: 'Trend', prefixes: ['ema_', 'price_vs_ema', 'adx_', 'slope_', 'r_squared_'] },
  { label: 'Volatility', prefixes: ['atr_', 'bb_', 'garman_', 'mad_'] },
  { label: 'Volume', prefixes: ['volume_', 'obv_', 'vwap', 'price_vs_vwap', 'volume_weighted_'] },
  {
    label: 'Pattern',
    prefixes: ['double_bottom', 'fvg_', 'ob_', 'sfp_', 'mbos_', 'bos_', 'gr_zone'],
  },
  { label: 'S/R', prefixes: ['support_', 'resistance_', 'dist_to_'] },
  {
    label: 'Temporal',
    prefixes: ['hour_', 'day_of_week_', 'month_', 'minute_', 'is_us_', 'is_asia_'],
  },
  { label: 'Macro', prefixes: ['fear_', 'greed_', 'btc_dominance', 'vix_', 'treasury_', 'dxy_'] },
];

// =============================================================================
// Signal marker confidence visual (re-export SoT for Plotly callers)
// =============================================================================

export {
  confidenceToOpacity,
  confidenceToPlotlyEntryMarkerSize,
} from '@/utils/signal-marker-confidence-visual';

/** Dynamic regime hint markers: larger and high-contrast for dense candle areas. */
export const DYNAMIC_REGIME_HINT_MARKER_SIZE = 11;
export const DYNAMIC_REGIME_HINT_MARKER_OPACITY = 1;
export const DYNAMIC_REGIME_HINT_MARKER_STROKE_WIDTH = 2;
