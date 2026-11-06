"""HTTP rate limits by route and tier (settings §18)."""

from typing import Final, Literal

from pydantic import Field

# Local-dev research sweeps (five-mode exhaustive, walk-forward batches) need
# headroom beyond prod admin defaults. Applied in Settings validator when
# environment=development only — staging/production keep 600/1200.
DEVELOPMENT_BACKTEST_RUN_RATE_LIMIT_ADMIN_PER_MINUTE: Final[int] = 6000
DEVELOPMENT_BACKTEST_RUN_RATE_LIMIT_SUPER_ADMIN_PER_MINUTE: Final[int] = 12000


class SettingsOpsRateLimitsMixin:
    rate_limit_backend: Literal["memory", "redis"] = "memory"

    # --- Public read endpoints (no auth) — prevent scrape/DoS amplification ---
    # GET /health/catalog — public indicator-catalog counts (not a probe), per IP.
    # /health and /ready stay limiter-free (probe contract; liveness must not
    # depend on Redis). 60/min is generous for ops dashboards / FE diagnostics.
    health_catalog_rate_limit_per_minute: int = 60

    # --- Public write endpoints (no auth) — prevent DoS/abuse ---
    signals_generate_rate_limit_per_minute: int = 10  # POST /signals/generate per IP
    newsletter_subscribe_rate_limit_per_minute: int = 5  # POST /newsletter_subscribers per IP
    contact_inquiry_rate_limit_per_minute: int = 5  # POST /contact_inquiries per IP

    # --- Backtest run: request-throttle policy by identity/tier (not quota caps) ---
    # Anonymous/paid tiers stay tight (abuse + compute protection). Admin/super-admin
    # run research sweeps (lever scans, walk-forward batches) that legitimately fire
    # many backtests per minute, so their ceilings are generous research headroom —
    # bounded (not unlimited) to keep the fail-closed abuse contract intact, and
    # backstopped by per-user quota + AdminBaselineRateLimitMiddleware.
    # NOTE: Settings elevates admin/super_admin in environment=development (see
    # DEVELOPMENT_BACKTEST_RUN_RATE_LIMIT_* in this module).
    backtest_run_rate_limit_anonymous_per_minute: int = 5
    backtest_run_rate_limit_free_per_minute: int = 10
    backtest_run_rate_limit_starter_per_minute: int = 10
    backtest_run_rate_limit_pro_per_minute: int = 20
    backtest_run_rate_limit_elite_per_minute: int = 60
    backtest_run_rate_limit_admin_per_minute: int = 600
    backtest_run_rate_limit_super_admin_per_minute: int = 1200

    # --- Backtest compare: tier-aware compute protection ---
    backtest_compare_rate_limit_free_per_minute: int = 5
    backtest_compare_rate_limit_starter_per_minute: int = 10
    backtest_compare_rate_limit_pro_per_minute: int = 20
    backtest_compare_rate_limit_elite_per_minute: int = 30
    backtest_compare_rate_limit_admin_per_minute: int = 60
    backtest_compare_rate_limit_super_admin_per_minute: int = 120

    # --- Backtest hub: elite+admin heavy compute protection ---
    backtest_hub_optimize_rate_limit_per_minute: int = 30
    backtest_hub_walk_forward_rate_limit_per_minute: int = 20
    backtest_hub_monte_carlo_rate_limit_per_minute: int = 30

    # --- Auth abuse-surface route throttles ---
    auth_register_rate_limit_per_minute: int = 10
    auth_refresh_rate_limit_per_minute: int = 30
    auth_reset_password_rate_limit_per_minute: int = 10
    oauth_rate_limit_per_minute: int = 10
    auth_profile_mutation_rate_limit_per_minute: int = 60
    auth_telegram_mutation_rate_limit_per_minute: int = 60

    # --- Billing route throttles ---
    billing_checkout_rate_limit_per_minute: int = 20
    billing_portal_rate_limit_per_minute: int = 30
    billing_webhook_rate_limit_per_minute: int = 120
    billing_pricing_click_rate_limit_per_minute: int = 30
    billing_invoices_read_rate_limit_per_minute: int = 30
    billing_invoices_export_rate_limit_per_minute: int = 10

    # --- User resource mutation throttles ---
    user_backtests_duplicate_rate_limit_per_minute: int = 60
    user_backtests_mutation_rate_limit_per_minute: int = 60
    public_backtest_catalog_rate_limit_per_minute: int = 30
    user_backtest_comparisons_mutation_rate_limit_per_minute: int = 60

    # --- Signal read delay policy by tier (seconds). 900 = 15 minutes ---
    signal_read_delay_free_seconds: int = 900
    signal_read_delay_starter_seconds: int = 900
    signal_read_delay_pro_seconds: int = 0
    signal_read_delay_elite_seconds: int = 0
    signal_read_delay_admin_seconds: int = 0
    signal_read_delay_super_admin_seconds: int = 0

    # --- Market & AI mock throttles ---
    ai_mock_mode_rate_limit_per_minute: int = 30
    market_chart_indicators_rate_limit_per_minute: int = 60
    market_liquidation_heatmap_rate_limit_per_minute: int = 30
    # GET /market/ohlcv — per client IP (see require_market_ohlcv_rate_limit; route itself requires auth)
    market_ohlcv_rate_limit_per_minute: int = 60
    # GET /sentiment/* — authenticated product reads; per user+IP
    sentiment_read_rate_limit_per_minute: int = 120
    # POST /trading/orders — authenticated mutations; per user+IP (abuse / hammering)
    trading_order_rate_limit_per_minute: int = 60
    # POST /trading/orders with market_type='swap' — admin-only futures; stricter limit
    futures_trading_order_rate_limit_per_minute: int = 10
    # POST /trading/orders/cancel — dedicated cancel bucket (per user+IP). Separated from
    # ``trading_order_rate_limit_per_minute`` so a cancel storm (stop-loss cascade, UI bulk
    # cancel) cannot starve order placement, and vice versa. Default matches placement
    # generosity; tune independently if cancel volume spikes under load.
    trading_order_cancel_rate_limit_per_minute: int = 60
    # POST /trading/reset — demo portfolio reset; tighter than orders (spam / DB churn)
    trading_reset_rate_limit_per_minute: int = 30
    # GET /trading/* authenticated reads — per user+IP (separate buckets so portfolio polling does not
    # starve trades/orders list fetches; parity with sentiment_read / fundamental_read).
    trading_portfolio_read_rate_limit_per_minute: int = 120
    trading_trades_read_rate_limit_per_minute: int = 120
    trading_orders_list_read_rate_limit_per_minute: int = 120
    trading_modes_read_rate_limit_per_minute: int = 120
    # POST /trading/mode-selection — audit-only mode switch (client UI); per user+IP
    trading_mode_selection_rate_limit_per_minute: int = 60
    # GET /trading/automations* — list/detail/active reads
    trading_automation_read_rate_limit_per_minute: int = 60
    # POST/PATCH /trading/automations — mutations (stricter than reads)
    trading_automation_mutation_rate_limit_per_minute: int = 10
    # User exchange connections (/exchanges/*) — per user+IP unless noted
    exchange_connect_rate_limit_per_minute: int = 5  # POST /exchanges/connect (secrets)
    exchange_verify_rate_limit_per_minute: int = 10  # POST /exchanges/{id}/verify (CCXT)
    exchange_balance_read_rate_limit_per_minute: int = 20  # GET /exchanges/{id}/balance
    exchange_disconnect_rate_limit_per_minute: int = 5  # DELETE /exchanges/{id}
    exchange_list_read_rate_limit_per_minute: int = 30  # GET /exchanges
    exchange_leverage_tiers_read_rate_limit_per_minute: int = 10  # GET /exchanges/{id}/leverage-tiers
    exchange_supported_catalog_rate_limit_per_minute: int = 60  # GET /exchanges/supported (public, per IP)

    # GET /fundamental/onchain (Redis snapshot read) — separate bucket from sentiment so dashboard
    # polls to both endpoints do not double-count against a single limiter.
    fundamental_read_rate_limit_per_minute: int = 120

    # --- Dashboard Live Signal: agent card display weights (also in GET /config/public) ---
    agent_breakdown_technical_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    agent_breakdown_market_mood_weight: float = Field(default=0.1, ge=0.0, le=1.0)
    agent_breakdown_news_sentiment_weight: float = Field(default=0.05, ge=0.0, le=1.0)
    agent_breakdown_on_chain_weight: float = Field(default=0.05, ge=0.0, le=1.0)
    # Multipliers applied to the Technical card display weight when the latest signal has
    # numeric indicator payload and/or classic rules fired (bounded; two knobs, not env soup).
    agent_breakdown_signal_technical_boost_indicators: float = Field(
        default=1.22,
        ge=1.0,
        le=2.0,
        description="Boost factor when signal carries numeric technical indicators (display weight only).",
    )
    agent_breakdown_signal_technical_boost_classic: float = Field(
        default=1.12,
        ge=1.0,
        le=2.0,
        description="Boost factor when classic / chart-strategy rules fired on the signal (display weight only).",
    )

    # --- Admin panel throttles ---
    admin_user_detail_read_rate_limit_per_minute: int = 120
    admin_user_detail_mutation_rate_limit_per_minute: int = 30
    admin_billing_read_rate_limit_per_minute: int = 60
    admin_billing_mutation_rate_limit_per_minute: int = 20
    admin_announcement_read_rate_limit_per_minute: int = 20
    admin_announcement_mutation_rate_limit_per_minute: int = 5
    # AI Strategy Assistant (Initiative 4): kept low because each call hits the
    # Anthropic API (real $ cost). Five per minute is plenty for human review
    # workflow and bounds runaway loops if a script ever holds an admin token.
    admin_strategy_draft_generate_rate_limit_per_minute: int = 5
    # Training mutation endpoints (POST /train, POST /jobs, POST /jobs/batch,
    # POST /ensemble/*/train) kick off real ML training that bills cloud
    # compute (GPU/CPU) for minutes-to-hours. A compromised admin token that
    # spams these would be expensive fast. 3/min is plenty for legitimate use.
    admin_training_mutation_rate_limit_per_minute: int = 3
    # Blanket per-(admin, IP) ceiling applied by AdminBaselineRateLimitMiddleware
    # to every /api/v1/admin/* request. Acts as a backstop for endpoints that
    # don't yet have a per-endpoint dep, and as defense in depth for those that
    # do. Tuned generously so legitimate admin UI use (occasional bursts of
    # table reads) is unaffected; a compromised token can't sustain abuse.
    admin_baseline_rate_limit_per_minute: int = 240
    # Set to False to disable the baseline (e.g. for soak tests that need
    # higher fan-out). Production keeps it on.
    admin_baseline_rate_limit_enabled: bool = True
    # Application logs can contain user IDs, paths, IPs; an admin holding a
    # compromised token could exfiltrate large volumes by polling /admin/logs.
    # 120/min is generous for human use but prevents bulk dumping.
    admin_logs_read_rate_limit_per_minute: int = 120
    # System-control mutations (override deletes) change runtime behavior; a
    # rapid burst could thrash training/backtest dispatchers. Super-admin only,
    # plus this cap as defense in depth.
    admin_system_controls_mutation_rate_limit_per_minute: int = 10
    admin_model_lifecycle_mutation_rate_limit_per_minute: int = 10
    # super_admin gets a higher ceiling: bulk cleanup hard-deletes one version per call, and a model
    # can have dozens of versions (research training), so the base admin cap blocks legit cleanup.
    admin_model_lifecycle_mutation_rate_limit_super_admin_per_minute: int = 300
    admin_vip_issue_code_rate_limit_per_minute: int = 10
    admin_vip_invite_email_rate_limit_per_minute: int = 5
    admin_announcement_batch_size: int = 500
    admin_announcement_pause_between_batches_seconds: float = 0.0
