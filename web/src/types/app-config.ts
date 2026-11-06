/**
 * Public app config types (GET /api/v1/config/public).
 * Used by useAppConfig and useTradingConfig.
 */

export type FeaturesConfig = {
  backtest: boolean;
  /**
   * Global gate for server-mediated live execution in the automation pipeline
   * (Celery). Manual /trade live trading is always browser-direct via
   * /dashboard/live-direct (Tealstreet pattern); this flag does not affect
   * the manual UI.
   */
  live_trading: boolean;
  visual_patterns: boolean;
  /** Server kill-switch: non-admin Spot↔Futures UI on paper **and** live when exchange supports swap. */
  futures_paper_trading: boolean;
  /** Super-admin inference compare API + /admin/inference-compare (server kill-switch). */
  inference_compare: boolean;
};

/**
 * SoT accessor for `features` on GET /config/public — use instead of string literals at call sites.
 * Must stay in sync with :class:`FeaturesConfig` and BE ``config_schemas``.
 */
export const FEATURES_CONFIG_KEY_FUTURES_TRADING_UI =
  'futures_paper_trading' as const satisfies keyof FeaturesConfig;

/**
 * Wire keys for GET /config/public ``features`` — use for bracket access and offline fallback.
 * Futures UI reuses ``FEATURES_CONFIG_KEY_FUTURES_TRADING_UI`` so rename stays one-edit.
 */
export const FEATURES_CONFIG_KEYS = {
  backtest: 'backtest',
  live_trading: 'live_trading',
  visual_patterns: 'visual_patterns',
  futures_paper_trading: FEATURES_CONFIG_KEY_FUTURES_TRADING_UI,
  inference_compare: 'inference_compare',
} as const satisfies { readonly [K in keyof FeaturesConfig]: K };

/** Pairs with ``FEATURES_CONFIG_KEY_FUTURES_TRADING_UI`` for ``Pick<FeaturesConfig, …>`` without duplicating the field name. */
export type FeaturesConfigFuturesTradingUiKey = typeof FEATURES_CONFIG_KEY_FUTURES_TRADING_UI;

type LimitsConfig = {
  max_backtest_days: number;
  max_positions: number;
  /** Platform minimum for signal/backtest confidence sliders (percent 0–100). SoT: BE. */
  min_signal_confidence_percent: number;
  /** Effective global cap on stored model versions (env + optional runtime override). */
  max_stored_model_versions: number;
};

/** Runtime operator pause flags (GET /config/public). */
type SystemControlsPublicConfig = {
  training_dispatch_paused: boolean;
  backtest_paused: boolean;
};

type SelectOption = {
  value: string;
  label: string;
};

export type ExitStrategyFieldConfig = {
  key: string;
  /** BE-served default; null = caller must supply (e.g. stop_loss_pct). */
  default?: number | null;
};

export type ClassicSignalOptionConfig = {
  value: string;
  label: string;
  description: string;
  confidence: number;
  detector_id: string;
};

export type IndicatorCatalogCountsConfig = {
  chart_indicator_columns: number;
  tradable_classic_signals: number;
  classic_registry_total: number;
  feature_columns: number;
  display_indicators: number;
};

type BacktestConfig = {
  exit_strategy_options: SelectOption[];
  default_exit_strategy: string;
  exit_strategy_fields: Record<string, ExitStrategyFieldConfig[]>;
  classic_signal_options?: ClassicSignalOptionConfig[];
};

export type TrainingConfig = {
  optimization_objectives: Record<string, string[]>;
  model_types: string[];
  target_types: string[];
  objective_labels: Record<string, string>;
  model_type_options: SelectOption[];
  target_type_options: SelectOption[];
  experimental_target_types?: string[];
  experimental_target_type_options?: SelectOption[];
  objective_options: SelectOption[];
  training_window_options: SelectOption[];
  default_training_window: number;
  optimization_mode_options: SelectOption[];
  default_optimization_mode: string;
  suggested_trials_by_mode?: Record<string, number>;
  model_type_directions: Record<string, string[]>;
  available_feature_count?: number;
  default_max_features: number;
};

type UIConfig = {
  default_theme: 'light' | 'dark' | 'system';
};

/** Live Signal agent card weights (snake_case JSON from GET /config/public). */
type AgentBreakdownWeightsConfig = {
  technical: number;
  market_mood: number;
  news_sentiment: number;
  on_chain: number;
};

/** Candle display + on-demand generate auth policy (GET /config/public). */
type SignalsPublicConfig = {
  /** IANA zone for persisted candle local ISO when API has no user TZ and body omits display_timezone; Celery uses the same default. */
  signal_display_timezone_default: string;
  /** When true, POST /signals/generate requires a valid session. */
  signal_generate_requires_authentication: boolean;
  /** Resolved LIVE_STEP tail length (closed bars) for Celery OHLCV — same N as inference narrow tooling. */
  live_ohlcv_tail_bar_count: number;
  /** When true, Celery fetches N+buffer then narrows with build_live_contract_slice (server env). */
  live_signal_wide_fetch_then_live_step_slice: boolean;
  /** Extra bars when wide fetch is on (server env). */
  live_signal_wide_fetch_buffer_bars: number;
};

export type TimeframePublicOption = {
  value: string;
  ms: number;
  label: string;
  /**
   * Candles the chart should request for this timeframe — SERVER-OWNED.
   *
   * The chart-indicators response cache is keyed by `limit`, so a client that derives its own
   * value and disagrees with the server requests a key nothing warmed and pays the cold path:
   * measured 1308ms at 5m/4032 on prod 2026-09-06, against 397ms warm. Consuming this instead of
   * recomputing is what keeps the two sides from drifting apart silently.
   *
   * Optional because a cached older API response, or the offline fallback, may not carry it —
   * callers fall back to the local derivation in that case.
   */
  chart_candle_limit?: number;
};

export type PublicConfig = {
  environment: 'development' | 'staging' | 'production';
  symbols: string[];
  free_tier_allowed_symbols: string[];
  timeframes: string[];
  /** Registry-backed metadata from BE TIMEFRAME_REGISTRY (ms + label). */
  timeframe_options?: TimeframePublicOption[];
  exchanges: string[];
  features: FeaturesConfig;
  limits: LimitsConfig;
  system_controls: SystemControlsPublicConfig;
  training: TrainingConfig;
  backtest: BacktestConfig;
  catalog_counts?: IndicatorCatalogCountsConfig;
  ui?: UIConfig;
  agent_breakdown_weights: AgentBreakdownWeightsConfig;
  signals: SignalsPublicConfig;
};

export type UseAppConfigReturn = {
  config: PublicConfig;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
};
