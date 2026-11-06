/**
 * Extended constants (AI, HTTP, chart, UI, API paths, ensemble).
 * §7.2 CODING_STANDARDS: TS general cap 400 lines. Split from monolith constants.ts.
 */

import { MIN_SIGNAL_CONFIDENCE_PERCENT } from '@pulsai/shared';

import { EXIT_STRATEGIES, SIGNAL_ACTIONS } from '@/utils/constants/core';
import type { SignalAction } from '@/utils/constants/core';

// ============================================================================
// ML Confidence display
// ============================================================================

export const ML_CONFIDENCE_DECIMAL_PLACES = 6;

// ============================================================================
// Admin AI – Provider display and strategy (ADR-010)
// ============================================================================

export const AI_PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  mock: 'Mock (Development)',
  groq: 'Groq (Llama 3)',
  claude: 'Claude (Anthropic)',
  gemini: 'Gemini (Google)',
  openrouter: 'OpenRouter',
  together: 'Together AI',
};

export const AI_PROVIDER_STRATEGY = [
  { tier: 'Free/Starter', provider: 'Groq (Llama 3)', reason: 'fastFreeGood' },
  { tier: 'Pro/Elite', provider: 'Claude', reason: 'premiumVision' },
] as const;

// ============================================================================
// HTTP Status Codes
// ============================================================================

export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  ACCEPTED: 202,
  NO_CONTENT: 204,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  RATE_LIMIT: 429,
  NOT_IMPLEMENTED: 501,
} as const;

// ============================================================================
// Polling/Refresh Intervals
// ============================================================================

export const POLL_INTERVALS = {
  REALTIME: 2000,
  STANDARD: 30000,
  SLOW: 60000,
  RECONNECT: 3000,
  FETCH_TIMEOUT: 10000,
  /** Second signal-history fetch after bar close (ML signal may land after kline finalize). */
  SIGNAL_HISTORY_AFTER_BAR_CLOSE_MS: 2_500,
  /**
   * Delay dashboard/full OHLCV refetch after kline finalize so BE/Redis tail can catch up;
   * `realtime-candles-closed-cache` bridges the gap until this fires.
   */
  CHART_OHLCV_REFETCH_AFTER_BAR_CLOSE_MS: 1_200,
} as const;

// ============================================================================
// Period Options
// ============================================================================

export const PERIOD_OPTIONS = {
  '24h': { hours: 24, label: '24 Hours' },
  '7d': { hours: 168, label: '7 Days' },
  '30d': { hours: 720, label: '30 Days' },
} as const;

export type PeriodOption = keyof typeof PERIOD_OPTIONS;

// ============================================================================
// User Status Constants
// ============================================================================

// ============================================================================
// Responsive Breakpoints (must mirror tailwind.config / Tailwind defaults)
// ============================================================================

/** Tailwind `md` breakpoint — below this the sidebar collapses by default. */
export const MOBILE_BREAKPOINT_PX = 768;

// ============================================================================
// Storage Keys
// ============================================================================

export const STORAGE_KEYS = {
  SELECTED_SYMBOL: 'pulsai_selected_symbol',
  /** Scoped by user id (`:userId`) — persisted `TradingMode.id` for Demo/Paper toggle. */
  SELECTED_TRADING_MODE: 'pulsai_selected_trading_mode',
  AUTH_TOKENS: 'pulsai_auth_tokens',
  PREFERENCES: 'pulsai_preferences',
  /**
   * Full-chart indicator toggles — legacy unscoped key; active keys are
   * `:<userId|guest>:<timeframe>` via chart-indicator-preferences-storage.
   */
  CHART_INDICATOR_PREFERENCES: 'pulsai_chart_indicator_preferences',
  CHART_SELECTED_TIMEFRAME: 'pulsai_chart_selected_timeframe',
  CHART_TIMEZONE: 'pulsai_chart_timezone',
  BACKTEST_SHOW_R_LEVEL_GUIDES: 'pulsai_backtest_show_r_level_guides',
  BACKTEST_SHOW_LIQUIDATION_GUIDES: 'pulsai_backtest_show_liquidation_guides',
  BACKTEST_SHOW_LIQUIDATION_HEATMAP: 'pulsai_backtest_show_liquidation_heatmap',
  BACKTEST_SHOW_DYNAMIC_REGIME_HINTS: 'pulsai_backtest_show_dynamic_regime_hints',
  /** Prefix for chart zoom/pan persistence — @see chart-visible-range-storage.ts */
  CHART_VISIBLE_RANGE_V1_PREFIX: 'pulsai_chart_visible_range_v1:',
  SIDEBAR_COLLAPSED: 'pulsai_sidebar_collapsed',
  /** Scoped by user id (`:userId`) — paper order UX: manual vs policy-assisted automation hints. */
  TRADE_ORDER_INTENT: 'pulsai_paper_trade_order_intent',
} as const;

// ============================================================================
// Chart Indicator Constants
// ============================================================================

export const CHART_RSI_LEVELS = {
  OVERBOUGHT: 70,
  OVERSOLD: 30,
} as const;

export const CHART_SIGNAL_MARKER_COLORS: Record<SignalAction, string> = {
  [SIGNAL_ACTIONS.BUY]: '#26a69a',
  [SIGNAL_ACTIONS.SELL]: '#ef5350',
  [SIGNAL_ACTIONS.HOLD]: '#ffc107',
};

export const CHART_HIGHER_TF_MARKER_COLORS: Record<SignalAction, string> = {
  [SIGNAL_ACTIONS.BUY]: '#81c784',
  [SIGNAL_ACTIONS.SELL]: '#e57373',
  [SIGNAL_ACTIONS.HOLD]: '#ffca28',
};

/** When chart opts omit minConfidence, filter markers at platform minimum (SoT). */
export const CHART_FULL_PAGE_MIN_CONFIDENCE = MIN_SIGNAL_CONFIDENCE_PERCENT;

/**
 * ML signal markers on the live (forming) candle — single toggle for dashboard + full chart.
 *
 * - `false` (default): ML runs on **closed** bars only; markers on the forming bar are wrong.
 * - `true`: draw markers on the forming candle (legacy experiment; tooltip can still show ML via lookup).
 *
 * Optional `signalMarkersOnFormingCandle` on `buildDashboardMarkers` / `buildFullChartMarkers` overrides this for tests.
 * @see apps/web/src/utils/chart-sync-markers.ts
 */
export const CHART_SIGNAL_MARKERS_ON_FORMING_CANDLE = false;

/**
 * PoC: persist visible time range (zoom/pan) to localStorage — @see useChartVisibleRangePersistence.
 * Set false to disable save/restore on refresh.
 */
export const CHART_VISIBLE_RANGE_PERSISTENCE_ENABLED = true;

/**
 * Chart & signal limits – SoT for full-chart and useSignalEvents.
 * When BE exposes these (e.g. GET /config/public), FE can override from response.
 *
 * Chart: "last year" = up to CHART_MAX_DAYS of candles, capped by CHART_CANDLES_CAP.
 * Signals: "max 1 week" = candles in 7 days for that TF, capped by SIGNAL_MAX_WEEK_CAP.
 *
 * Dashboard/full-chart OHLCV requests must stay within GET /market/ohlcv and
 * GET /market/chart-indicators `limit` max (Query le=… on the API).
 */

/** Minimum visible history on dashboard + full chart for TFs without a per-TF override. */
export const CHART_MIN_HISTORY_DAYS = 2;
/**
 * Lower intraday TFs (5m/15m/30m): enough multi-session context for discretionary reading.
 * 15m×14d = 1344 bars; 5m×14d = 4032 → requires {@link MARKET_OHLCV_API_MAX_CANDLES} ≥ 4032.
 */
export const CHART_LOWER_TF_MIN_HISTORY_DAYS = 14;
/**
 * Per-TF history floor (days) — overrides the global ``CHART_MIN_HISTORY_DAYS``.
 *
 * Why not raise the global floor: coarse TFs already get deep windows via the
 * 200/500 candle floors; a global 14-day floor would inflate 1m/5m payloads
 * unnecessarily for hourly+ charts that do not need it.
 */
export const TIMEFRAME_HISTORY_DAYS_OVERRIDES: Readonly<Record<string, number>> = {
  '5m': CHART_LOWER_TF_MIN_HISTORY_DAYS,
  '15m': CHART_LOWER_TF_MIN_HISTORY_DAYS,
  '30m': CHART_LOWER_TF_MIN_HISTORY_DAYS,
};
/**
 * Must match FastAPI ``Query(..., le=…)`` / ``MARKET_CHART_OHLCV_MAX_LIMIT`` on
 * market OHLCV + chart-indicators. Sized for two weeks of 5m bars (14 × 288).
 */
export const MARKET_OHLCV_API_MAX_CANDLES = 4500;

/** Max signals to fetch/store = 1 week of candles for the TF, capped (e.g. 5m → 2016). */
export const SIGNAL_MAX_WEEK_CAP = 2500;

/** @deprecated Use getSignalLimitForTimeframe(timeframe) from chart-time. Fallback when TF unknown. */
export const SIGNAL_FETCH_HISTORICAL_LIMIT_FALLBACK = 200;
/** @deprecated Use getSignalLimitForTimeframe(timeframe). Fallback when TF unknown. */
export const SIGNAL_MAX_HISTORY_FALLBACK = 250;
/** Per higher-TF fetch: same formula as primary (1 week for that TF), no separate constant. */

/** Desktop / wide full-chart chrome offset (toolbar + legend, single row). */
export const FULL_CHART_VIEWPORT_OFFSET_PX = 120;

/** Tailwind `sm` breakpoint — below this, use {@link FULL_CHART_VIEWPORT_OFFSET_MOBILE_PX}. */
export const FULL_CHART_MOBILE_MAX_WIDTH_PX = 640;

/** Mobile / PWA: app header + wrapped toolbar + legend + safe area. */
export const FULL_CHART_VIEWPORT_OFFSET_MOBILE_PX = 248;

export const FULL_CHART_DEFAULT_HEIGHT_PX = 500;
export const FULL_CHART_MIN_HEIGHT_PX = 400;

/** Default height (px) for the backtest results / detail OHLC chart. */
export const BACKTEST_CHART_DEFAULT_HEIGHT_PX = 400;

/** Height (px) for the standalone equity-curve overlay chart on backtest detail. */
export const BACKTEST_EQUITY_CHART_HEIGHT_PX = 320;

/**
 * Readable height (px) for the main (price) pane on the full chart — the floor of
 * the count-aware stacked canvas height (see resolveFullChartCanvasHeight).
 */
export const FULL_CHART_PRICE_PANE_HEIGHT_PX = 460;

/** Readable height (px) added per enabled indicator pane (RSI/MACD/Hilbert/…). */
export const FULL_CHART_INDICATOR_PANE_HEIGHT_PX = 200;

export const CHART_VOLUME_BAR_COLORS = {
  BULLISH: 'rgba(34, 197, 94, 0.5)',
  BEARISH: 'rgba(239, 68, 68, 0.5)',
} as const;

export const CHART_SYNC_MODE = {
  DASHBOARD: 'dashboard',
  FULL: 'full',
} as const;

export type ChartSyncMode = (typeof CHART_SYNC_MODE)[keyof typeof CHART_SYNC_MODE];

export const CHART_SOURCE_TYPE = {
  TRAINING: 'training',
  MODEL: 'model',
} as const;
export const DIVERGENCE_TYPES = {
  BULLISH: 'bullish',
  BEARISH: 'bearish',
  HIDDEN_BULLISH: 'hiddenBullish',
  HIDDEN_BEARISH: 'hiddenBearish',
} as const;
// ============================================================================
// UI Constants
// ============================================================================

export const BACKTEST_DEFAULTS = {
  SYMBOL: 'BTC/USDT',
  TIMEFRAME: '1h',
  EXIT_STRATEGY: EXIT_STRATEGIES.FIXED_HOLDING,
  INITIAL_CAPITAL: 10000,
  HOLDING_PERIODS: 4,
  MIN_CONFIDENCE: MIN_SIGNAL_CONFIDENCE_PERCENT,
  MAX_POSITIONS: 1,
  RISK_REWARD_RATIO: 2.0,
  TRAIL_PCT: 0.5,
  TRAIL_ACTIVATION_PCT: 1.0,
  ATR_PERIOD: 14,
  ATR_MULTIPLIER: 2.0,
  /** Matches BE DEFAULT_BACKTEST_MIN_NET_PCT (min_profit_after_fees). */
  MIN_NET_PCT: 0,
  /** Matches BE DEFAULT_BACKTEST_MAX_SL_PCT (None = no cap for ATR). */
  MAX_SL_PCT: null,
} as const;

/** Fallback when API omits timeframe (e.g. GET /signals/latest item). §12: no magic strings. */
export const SIGNALS_TIMEFRAME_FALLBACK = '1h';

export const BACKTEST_RUN_PATH = '/api/v1/backtest/run';
export const BACKTEST_RUN_ASYNC_PATH = '/api/v1/backtest/run-async';
// Backtest Hub advanced endpoints (admin/super_admin OR elite).
export const BACKTEST_HUB_OPTIMIZE_PATH = '/api/v1/backtest-hub/optimize';
export const BACKTEST_HUB_WALK_FORWARD_OPTIMIZE_PATH = '/api/v1/backtest-hub/walk-forward-optimize';
export const BACKTEST_HUB_MONTE_CARLO_PATH = '/api/v1/backtest-hub/monte-carlo';

/** Canonical backend route; browser `EventSource` must use `resolveEventStreamUrl()` (same-origin `/api/v1` rewrite). */
export const AI_EXPLAIN_STREAM_PATH = '/api/v1/ai/explain-signal-stream';

// (No separate "public" constants: all hub calls use the unified /api/v1/backtest-hub/* SoT endpoints.)
/**
 * GET /api/v1/signals `per_page` for dashboard signal history.
 * Must match `SIGNALS_LIST_DEFAULT_PER_PAGE` in apps/api and stay ≤ API max (100).
 */
export const SIGNALS_LIST_PAGE_SIZE = 100;
export const TRAINING_JOBS_PAGE_SIZE = 100;

// ============================================================================
// Ensemble Constants (Sprint 2.9)
// ============================================================================

export const VOTING_STRATEGIES = [
  { value: 'soft', labelKey: 'ensemble.strategies.soft' },
  { value: 'hard', labelKey: 'ensemble.strategies.hard' },
  { value: 'max_prob', labelKey: 'ensemble.strategies.maxProb' },
  { value: 'confident_any', labelKey: 'ensemble.strategies.confidentAny' },
  {
    value: 'confident_majority',
    labelKey: 'ensemble.strategies.confidentMajority',
  },
  { value: 'unanimous', labelKey: 'ensemble.strategies.unanimous' },
  {
    value: 'confidence_weighted',
    labelKey: 'ensemble.strategies.confidenceWeighted',
  },
] as const;
export const WEIGHTING_METHODS = [
  { value: 'equal', labelKey: 'ensemble.weighting.equal' },
  { value: 'performance', labelKey: 'ensemble.weighting.performance' },
  { value: 'exponential_decay', labelKey: 'ensemble.weighting.expDecay' },
] as const;
