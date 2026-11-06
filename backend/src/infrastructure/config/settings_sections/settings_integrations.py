"""Settings mixin — Email, Billing, AI, Telegram, Exchanges (sections 4, 8-11)."""

from typing import Literal

from src.shared.constants.confidence import DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD
from src.shared.constants.email_assets import DEFAULT_LOCAL_FRONTEND_URL
from src.shared.constants.hunt_timeframes import TELEGRAM_NOTIFY_DEFAULT_TIMEFRAMES


class SettingsIntegrationsMixin:
    """Email, billing, AI, Telegram and exchange settings, mixed into Settings; the parsed lists below are plain
    properties -- nothing serializes Settings, so they need no computed_field (and no type: ignore for it)."""

    # ═══════════════════════════════════════════════════════════════════════════

    resend_api_key: str = ""
    email_from: str = "noreply@pulsai.live"
    frontend_url: str = DEFAULT_LOCAL_FRONTEND_URL  # For password reset links
    # WHY 10/day: Prevents spam abuse while allowing reasonable alerts
    # Signals typically fire 1-3 times per day per symbol
    email_alerts_rate_limit_per_day: int = 10  # Max signal alert emails per user per day
    # Weekly digest worker: DB keyset page size and optional pause between pages.
    weekly_digest_user_batch_size: int = 500
    weekly_digest_pause_between_batches_seconds: float = 0.0
    # Weekly marketing newsletter: disabled by default until content + operations are ready.
    newsletter_broadcast_enabled: bool = False
    newsletter_broadcast_batch_size: int = 500
    newsletter_broadcast_pause_between_batches_seconds: float = 0.0
    # Long-term inactivity lifecycle: warning after 2 years, then purge 3 days after the warning email.
    account_inactivity_auto_purge_enabled: bool = False
    account_inactivity_warning_after_days: int = 730
    account_inactivity_grace_days_after_warning: int = 3
    account_inactivity_batch_size: int = 500
    account_inactivity_pause_between_batches_seconds: float = 0.0
    # Kill-switch for signal email alerts (TG alerts are not affected).
    # Set EMAIL_ALERTS_ENABLED=false in production to suppress all signal emails.
    email_alerts_enabled: bool = False
    # Inbound contact form notifications (Resend). Empty = DB-only, no email.
    contact_inquiry_notification_email: str = ""

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    stripe_secret_key: str = ""
    stripe_price_starter: str = ""  # price_… ID for Starter recurring line item
    stripe_price_pro: str = ""  # price_… for Pro (Sprint 3.4 multi-tier)
    stripe_price_elite: str = ""  # price_… for Elite (€49 self-serve); empty = tier not checkout-able
    # Optional USD Price IDs (same tiers; EUR remains default per ROADMAP ADR-011)
    stripe_price_starter_usd: str = ""
    stripe_price_pro_usd: str = ""
    stripe_price_elite_usd: str = ""
    stripe_webhook_secret: str = ""  # whsec_… for POST /billing/webhook signature verify
    stripe_checkout_success_path: str = "/dashboard?checkout=success"
    stripe_checkout_cancel_path: str = "/pricing?checkout=cancel"
    # Return URL after Stripe Customer Portal (manage subscription)
    stripe_billing_portal_return_path: str = "/dashboard/settings/billing"

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # Providers: "claude" (paid), "groq" (free text), "gemini" (free vision),
    #            "together" (free vision), "openrouter" (free vision), "mock" (dev)
    # Mock mode can be toggled via API for testing without AI costs
    # Signal explain: if the tier primary upstream fails (e.g. Claude credits), the API walks
    # the runtime chain in src.infrastructure.ai.providers (OpenRouter → Together → Gemini → Groq → mock).

    ai_provider: Literal["claude", "groq", "gemini", "together", "openrouter", "mock"] = (
        "openrouter"  # Default: OpenRouter (free vision, no credit card)
    )
    ai_mock_mode: bool = False  # Override: force mock responses (for dev/testing)

    # Anthropic Claude (paid, premium quality)
    # Get key from: https://console.anthropic.com/settings/keys
    anthropic_api_key: str = ""
    ai_model_claude: str = "claude-sonnet-4-6"

    # Groq (FREE tier, fast inference with Llama/Mixtral)
    # Get key from: https://console.groq.com/keys
    groq_api_key: str = ""
    #: Measured against the live Groq catalogue 2026-09-09: `llama-3.3-70b-versatile` returns
    #: 404 model_not_found — it was decommissioned upstream and this default had followed it into
    #: the grave. Groq carries no API key in prod today, so `is_configured()` is False there and
    #: the provider is skipped in the failover chain; the defect was LATENT, waiting for the day
    #: someone sets GROQ_API_KEY. It was not latent locally, where the key exists and every call
    #: 404'd. Verified present in `GET /openai/v1/models` at the time of the change.
    ai_model_groq: str = "openai/gpt-oss-120b"  # Free tier, strongest general model Groq serves

    # Google Gemini (FREE tier with vision support)
    # Get key from: https://aistudio.google.com/app/apikey
    gemini_api_key: str = ""
    ai_model_gemini: str = "gemini-2.0-flash"  # Free, fast, vision support (2026)

    # Together.ai (FREE tier with vision support - NO credit card required)
    # Get key from: https://api.together.xyz/settings/api-keys
    # Free vision 2026: meta-llama/Llama-Vision-Free (3.2 11B) or Llama-4-Scout below
    together_api_key: str = ""
    ai_model_together: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"  # Free, text
    # Free vision; alt: meta-llama/Llama-Vision-Free
    ai_model_together_vision: str = "meta-llama/Llama-4-Scout-17B-16E-Instruct"

    # OpenRouter (FREE tier with vision support - NO credit card required)
    # Get key from: https://openrouter.ai/keys
    # When 429: set AI_PROVIDER=together or gemini (see docs/09-research/FREE_VISION_APIS_2026.md)
    # List free vision models: python scripts/list_openrouter_models.py
    # Chart Analyze (screen-capture → H&S / inverse / Bulkowski): needs IMAGE modality.
    # MEASURED 2026-08-25: deepseek/deepseek-v4-flash-vision-exp is text+image in catalogue but
    # OpenRouter returns HTTP 404 under this account's privacy/ZDR guardrails — Analyze Chart
    # was broken on that pin. google/gemini-3.5-flash-lite: text+image, HTTP 200, Bulkowski
    # smoke PASS 4/4 on 4h/8h/12h/1d. Re-try DeepSeek only after privacy allows its providers.
    # List: python scripts/list_openrouter_models.py
    openrouter_api_key: str = ""
    ai_model_openrouter: str = "google/gemma-3-27b-it:free"
    # Primary OpenRouter vision slug (chart Analyze). When this fails with credit/privacy,
    # runtime chain falls to *native* Gemini (gemini_api_key) — not another OR slug.
    ai_model_openrouter_vision: str = "google/gemini-3.5-flash-lite"
    # Within-OpenRouter retry only (e.g. primary DeepSeek vision 404 privacy → try this).
    # Does NOT help when OpenRouter credits are $0 — that needs native Gemini.
    ai_model_openrouter_vision_fallback: str = "google/gemini-3.5-flash-lite"

    # News-impact (Phase 2) classification model — routed to the OpenRouter slot of the news
    # chain only (NOT explain/vision, which keep ai_model_openrouter). Validated 2026-06 in an
    # offline evaluation: DeepSeek-V3 ~89% macro accuracy vs FinBERT
    # ~44%, a few cents/day under the per-cycle cap + 6h cache. Paid slug for stability — the $0
    # `deepseek/deepseek-chat` alias's free tier is not guaranteed and 402s on a zero-credit key.
    ai_model_news_impact: str = "deepseek/deepseek-chat-v3-0324"

    # Common AI settings
    ai_max_context_tokens: int = 8000
    ai_temperature: float = 0.3  # Low = more factual, less creative
    ai_rate_limit_per_minute: int = 10  # Max AI product requests per authenticated user per minute

    # AI Language settings
    # WHY configurable: Different deployments target different markets
    # (LATAM = Spanish, US = English, etc.)
    ai_default_language: str = "es"  # ISO 639-1 code (es=Spanish, en=English)
    ai_supported_languages: str = "es,en,fr,it,pt,de"  # Comma-separated ISO codes

    @property
    def ai_supported_languages_list(self) -> list[str]:
        """Parse supported AI languages from comma-separated string."""
        return [lang.strip() for lang in self.ai_supported_languages.split(",") if lang.strip()]

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    telegram_bot_token: str = ""
    telegram_admin_chat_ids: str = ""
    """Comma-separated Telegram chat IDs for admin notifications (rollback, cleanup alerts)."""

    @property
    def telegram_admin_chat_ids_list(self) -> list[int]:
        """Parsed admin Telegram chat IDs."""
        import contextlib

        raw = (self.telegram_admin_chat_ids or "").strip()
        if not raw:
            return []
        result: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if part:
                with contextlib.suppress(ValueError):
                    result.append(int(part))
        return result

    # Timeframes for which we send a single-signal TG push (comma-separated).
    # Empty = send for all TFs (backward compatible).
    # Default: WHOLE trainable clock (LTF+HTF) — SoT: TELEGRAM_NOTIFY_DEFAULT_TIMEFRAMES.
    # Pattern SCOUT FYIs use a SEPARATE narrower gate: BULKOWSKI_PATTERN_NOTIFY_TIMEFRAMES.
    # Example override: "1h" or "30m,1h"
    telegram_notify_timeframes: str = ",".join(TELEGRAM_NOTIFY_DEFAULT_TIMEFRAMES)

    @property
    def telegram_notify_timeframes_list(self) -> list[str]:
        """Parsed allowlist for TG single-signal push. Empty list = notify all TFs (SoT)."""
        raw = (self.telegram_notify_timeframes or "").strip()
        if not raw:
            return []
        return [t.strip() for t in raw.split(",") if t.strip()]

    # Only send BUY/SELL to TG; HOLD is not actionable and noisy. Set True for debugging.
    telegram_notify_hold: bool = False
    # Min confidence (0-1) to send signal to TG. 0 = no filter. Aligns with signal_min_confidence_percent.
    telegram_min_confidence: float = DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD

    # Multi-indicator classic confluence TG (consolidated message per symbol + timeframe set).
    # OFF by owner decision 2026-09-02. The per-timeframe "Classic confluence: BTC - 1h" bulletins
    # (chart pattern / sr test / macd divergence / stochastic crossover) were noise in the channel:
    # they fire per timeframe AND again per timeframe-set, so one symbol produced three messages
    # for the same observation. The ML "CONFLUENCE DETECTED ... 2/3 TFs" alert is unaffected — it
    # is dispatched by `notify_confluence` BEFORE this gate in `detect_and_notify_confluences`.
    # Set TELEGRAM_CLASSIC_CONFLUENCE_ENABLED=true to bring them back.
    telegram_classic_confluence_enabled: bool = False
    # Reserved: classic TA Telegram without ML production models (2+ TA conditions).
    # Dispatch not implemented; when added, skip if False. Default True = opt-in when shipped.
    telegram_classic_pure_ta_enabled: bool = True

    # Economic calendar Telegram (pre/post event tiers, minutes)
    telegram_econ_pre_event_tiers: str = "60,30,15,5"
    telegram_econ_post_event_tiers: str = "1,5"
    telegram_econ_alerts_enabled: bool = True
    telegram_econ_alert_events: str = "fomc,cpi,nfp"
    telegram_econ_alert_dedup_ttl_seconds: int = 7200

    # Tradable-signal Telegram alerts (edge-book book/regime, carry funding direction).
    # ON by default; local-safe (the bot only sends when configured) + Redis-deduped, so an alert
    # fires once per genuine state change. Set the env flag to false to silence a surface.
    edge_book_alerts_enabled: bool = True
    carry_funding_alerts_enabled: bool = True
    # Bulkowski pattern SCOUT FYI (side/entry/target/hit%). Delivery also requires
    # pattern_alert_coverage_ready() — all ALIGNMENT TFs measured first.
    telegram_bulkowski_pattern_alerts_enabled: bool = True
    carry_execution_alerts_enabled: bool = True
    signal_alert_dedup_ttl_seconds: int = 86400

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    binance_api_key: str = ""
    binance_secret_key: str = ""
    # NOTE: testnet=False for data fetching (public endpoints don't need auth)
    # Only use testnet=True for actual trading in dev environment
    binance_testnet: bool = False
    # Cloudflare-Worker REST proxy base URL — empty by default (direct
    # `api.binance.com`). Set BINANCE_API_BASE_URL on services whose Railway
    # egress is geo-blocked by Binance (Railway Metal IPs get HTTP 451). The
    # consuming helper is in `infrastructure/exchange/binance_rest_url_override.py`.
    binance_api_base_url: str = ""

    #: Cloudflare Worker base URL for Hyperliquid, e.g. ``https://x.workers.dev``. Empty = talk to
    #: the venue directly, which is the default and the right one for local development.
    #:
    #: Set this on a service whose egress Hyperliquid has rate-blocked. Measured 2026-09-09: the
    #: `celery-worker` egress got 429 on the whale sweep's first call while two sibling services on
    #: different IPs got 200 in the same minutes, so the limit follows the IP, not the account.
    #: `hyperliquid_url_override` turns this into ``<base>/hl/info`` -- the namespace matters, the
    #: Worker 404s an unknown prefix.
    hyperliquid_api_base_url: str = ""
    # Slice 1b — Cloudflare-Worker WS proxy base URL (wss://...). Same Worker
    # as REST; dispatches on `Upgrade: websocket` header. Empty by default.
    # Consumer: `infrastructure/exchange/binance_ws_url_override.py` rewrites
    # `urls['api']['ws']` on ccxt.pro instances; `websocket_client.py`'s
    # binance-kline-fastpath URI also reads it.
    binance_ws_base_url: str = ""

    bitget_api_key: str = ""
    bitget_secret_key: str = ""
    bitget_passphrase: str = ""

    # Bitget DEMO ("paper trading") API key — a SEPARATE key created in Bitget Demo mode
    # (Demo mode -> Personal Center -> API Key Management -> Create Demo API Key). REQUIRED to reach
    # the "Demo Trading" USDT-M wallet the operator sees: the LIVE key above returns 40099 ("exchange
    # environment is incorrect") under set_sandbox_mode(True), because live keys cannot access the demo
    # environment (confirmed 2026-07-03). Empty = demo exchange execution unavailable (NO fallback to
    # the live keys — that fallback is what 40099s). See src/application/services/edge_book_execution_ccxt.
    bitget_demo_api_key: str = ""
    bitget_demo_secret_key: str = ""
    bitget_demo_passphrase: str = ""

    # MEXC USDT-M (demo / paper only). One key serves both hosts, so the order path pins the demo host.
    mexc_api_key: str = ""
    mexc_secret_key: str = ""

    # ── PulsAI Carry execution (delta-neutral funding carry) ──
    # SAFE DEFAULTS: nothing trades until carry_execution_enabled=true AND carry_dry_run=false.
    # carry_kill_switch overrides everything (halt). sandbox=true -> Bitget DEMO.
    #
    # Exchange connection SoT: set carry_exchange_connection_id to the UUID of an active
    # ExchangeConnection row (created via /admin/exchange-connections). When set, the carry
    # loop and stop/flatten resolve credentials via ExchangeConnectionService (encrypted keys
    # from the DB) instead of the env-based bitget_api_key / bitget_secret_key / bitget_passphrase
    # fields. Empty string = legacy env-key path (Hyperliquid split topology continues to use env).
    carry_exchange_connection_id: str = ""  # UUID of the carry ExchangeConnection; "" = env fallback
    carry_execution_enabled: bool = False  # master switch for the carry rebalance loop
    carry_dry_run: bool = True  # compute + log intents, place no orders
    carry_kill_switch: bool = False  # hard halt, overrides enabled
    carry_sandbox: bool = True  # demo/testnet endpoints
    carry_venue: str = "bitget"  # execution venue (CEX, same-leg topology)
    # "" = single-venue (perp on carry_venue); "hyperliquid" = split topology (spot on the CEX, short
    # perp on HL for ~hourly funding). HL live placement still requires funded HL wallet credentials.
    carry_split_perp_venue: str = ""
    carry_base: str = "BTC"  # base asset to run the carry on
    carry_capital_usd: float = 1000.0  # capital to deploy per the sizing engine
    carry_target_leverage: float = 3.0  # leverage ceiling fed to the sizer/rebalancer
    # Hyperliquid split topology (Slice 5b): CEX spot + Hyperliquid perp. HL is a DEX — auth is a
    # wallet address + EVM private key, NOT api key/secret. Empty by default.
    hyperliquid_wallet_address: str = ""
    hyperliquid_private_key: str = ""

    # Edge Book (cross-sectional derivatives book — CANDIDATE) execution gates. Carry-parity:
    # env-driven, admin-toggleable. LIVE is blocked until the book is certified (F1-F3 forward
    # gates) — an unproven candidate cannot place real-money orders, by construction (see
    # edge_book_execution_mode.resolve_execution_mode). Demo/sandbox is the only certifying path.
    # Carry-parity bool toggles (system-controls-overridable at runtime, no restart). The effective
    # mode derives from these: not enabled -> DISABLED; enabled + sandbox -> DEMO; enabled + not
    # sandbox -> LIVE (still cert-gated). kill_switch is env-only (emergency hard halt).
    edge_book_execution_enabled: bool = False  # master switch (ON/OFF)
    edge_book_kill_switch: bool = False  # hard halt, overrides enabled (env-only)
    edge_book_sandbox: bool = True  # DEMO (sandbox) vs LIVE (real money); default demo
    edge_book_capital_usd: float = 1000.0  # capital to deploy across the book
    edge_book_exchange_connection_id: str = ""  # demo Bitget ExchangeConnection UUID; "" = env

    # Portfolio books (XS trend, VT-17 momentum — insights PASS candidates). Off + demo by default.
    xs_trend_book_execution_enabled: bool = False
    xs_trend_book_sandbox: bool = True
    vt_17_momentum_execution_enabled: bool = False
    vt_17_momentum_sandbox: bool = True
    funding_ml_carry_execution_enabled: bool = False
    funding_ml_carry_sandbox: bool = True

    # Research loop (hypothesis queue orchestration — Phase 2). Off by default; no live orders.
    research_loop_enabled: bool = False
    # Hunt-loop sweep controls (toggled from the loop dashboard). High TFs (4h/8h/12h/1d) by default;
    # apply=false → dry-run (no result-JSON/ledger writes, no promote/R2) until an admin turns it on.
    research_loop_high_timeframes: bool = True
    research_loop_apply: bool = False

    # ═══════════════════════════════════════════════════════════════════════════
