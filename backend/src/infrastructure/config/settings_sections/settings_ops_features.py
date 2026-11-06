"""Feature flags and backtest limits (settings §15-17)."""

from typing import Final

from pydantic import Field

# Local dev: shorter historical backtest cache TTL so OOS sweeps do not bloat Redis.
DEVELOPMENT_BACKTEST_RESPONSE_CACHE_HISTORICAL_TTL_SECONDS: Final[int] = 14_400  # 4h


class SettingsOpsFeaturesMixin:
    # ═══════════════════════════════════════════════════════════════════════════
    # WHY: Different features enabled per environment (prod/staging/dev)
    # Toggle features without code changes via environment variables

    feature_backtest: bool = True  # Backtesting always enabled
    # Manual /trade live trading is browser-direct (Tealstreet) — the route
    # layer always rejects ``mode=live``. ``feature_live_trading`` is the
    # global gate for **automation** mainnet execution: when False, the
    # Celery auto-mode pipeline falls back to paper even if a connection has
    # ``mainnet_execution_enabled=True``.
    feature_live_trading: bool = Field(
        default=False,
        description=(
            "Global gate for server-mediated live execution in the automation "
            "pipeline (Celery). Manual /trade live trading is always "
            "browser-direct (rejected at the route layer)."
        ),
    )
    # Staging-only override: admins / super-admins can run mainnet automation
    # while the global ``feature_live_trading`` is off.
    feature_live_trading_internal_preview: bool = Field(
        default=False,
        description=(
            "Staging-only: admins/super-admins may run mainnet automation "
            "while ``feature_live_trading`` is off. Has no effect on manual "
            "/trade — that path is always browser-direct."
        ),
    )
    feature_visual_patterns: bool = False  # Claude Vision patterns (Sprint 2.7)
    chart_indicators_precompute_enabled: bool = Field(
        default=True,
        description=(
            "J4 supervisor-precompute kill-switch. When True, the OHLCV "
            "stream supervisor computes the full chart-indicators payload "
            "on every closed bar and writes it to Redis; the handler "
            "short-circuits on a hit. When False, both writer and reader "
            "are disabled — supervisor doesn't write, handler doesn't try. "
            "Belt-and-suspenders rollback: even with the writer disabled, "
            "the handler falls through to the existing path. See "
            "docs/04-structural/PLAN_chart_indicators_j4_supervisor_precompute.md §6."
        ),
    )
    # ``feature_paper_trading`` was dropped in Phase 5 — paper is no longer a
    # user-facing mode (the /trade UI shows DEMO + LIVE only). Automation still
    # uses ``paper`` internally as a partition value, but it doesn't need a
    # global gate; ``feature_live_trading`` controls automation host selection.
    feature_futures_paper_trading: bool = False  # Futures paper trading (admin-only)
    backtest_perp_tiered_mmr_allowed: bool = True

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    backtest_use_calculate_selected: bool = Field(
        default=False,
        description=(
            "When True, batch backtest uses calculate_selected (live-aligned) "
            "instead of calculate_all (training-aligned). "
            "Default False: calculate_all for training parity. "
            "Toggle to True for live-parity experiments (env BACKTEST_USE_CALCULATE_SELECTED)."
        ),
    )
    max_backtest_days: int = 365  # Max historical days for backtesting
    max_backtest_range_days: int = 3500  # Max start->end range (~9.6y; covers 2017→now inventory CryptoBT)
    backtest_range_days_free_tier_max: int = 90  # Free-tier hard cap for /backtest/run
    backtest_response_cache_ttl_seconds: int = 120  # Identical payload cache window (forming-candle range)
    backtest_response_cache_historical_ttl_seconds: int = 86400  # Cache window when range end is fully in the past (immutable OHLCV → deterministic)
    backtest_heavy_async_threshold_days: int = 180  # Suggest async queue above this range
    backtest_async_dedupe_window_seconds: int = 1800  # Deduplicate identical queued/running async requests
    hybrid_signal_neighborhood_candles: int = 0  # 0 = same-candle only; N = the last N candles
    ml_signal_neighborhood_candles: int = 0  # When 2+ models: agree within the last N candles (0 = same)
    max_positions: int = 3  # Max concurrent positions (Phase 4)
    # Backtest quota caps. Execution = rolling window (see window_hours); history = cumulative saved rows.
    backtest_quota_limit_free: int = 5
    backtest_quota_limit_starter: int = 10
    backtest_quota_limit_pro: int = 20
    backtest_quota_limit_elite: int = 40
    backtest_quota_limit_admin: int = 80
    backtest_quota_limit_super_admin: int = 20000
    # Rolling window (hours) for the backtest EXECUTION quota; 0 = lifetime cumulative count.
    backtest_execution_quota_window_hours: int = 24
    # POST /backtest/inference-compare: per user+IP (super_admin only)
    inference_compare_rate_limit_per_minute: int = 10
    # Kill-switch for ops (staging/prod); UI should hide when disabled via app config.
    inference_compare_api_enabled: bool = True
