"""Vendor timeouts, websocket, macro keys (settings §25-26)."""

from pydantic import AliasChoices, Field

from src.shared.constants.coinglass import COINGLASS_DEFAULT_BASE_URL


class SettingsOpsVendorsMixin:
    exchange_api_timeout: int = 30
    sentiment_api_timeout: int = 10
    # Headline sentiment worker: FinBERT in production (install .[headline-finbert] on Celery image).
    # pytest sets TESTING=true → classifier uses deterministic stub without torch.
    headline_sentiment_use_finbert: bool = True
    # Local dev without torch: set HEADLINE_SENTIMENT_ALLOW_STUB=true (never in production).
    headline_sentiment_allow_stub: bool = False
    # Optional Hugging Face Hub token — higher rate limits for ProsusAI/finbert cold start
    # (and research TabPFN/Kronos). Public FinBERT works without it; Hub warns if missing.
    # Set HF_TOKEN in apps/api/.env (gitignored). Applied to os.environ before download.
    hf_token: str = Field(
        default="",
        validation_alias=AliasChoices("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
    )
    # Phase 2: blend a lean LLM impact pass (macro-routed headlines) into the news
    # snapshot so geopolitical/macro headlines FinBERT scores NEUTRAL can move the card.
    # Auto-skips in stub mode (no real FinBERT) and degrades to FinBERT when no AI
    # provider key is set (chain falls to mock=NEUTRAL). Set False to force pure FinBERT.
    headline_news_impact_llm_enabled: bool = True

    # News-sentiment Telegram alert (admin-only first; default OFF — nothing sends until enabled).
    # Fires a high-conviction heads-up from the headline refresh task when the BLENDED directional
    # value clears the threshold with enough volume. Runtime-toggleable via system_controls.
    news_sentiment_tg_alert_enabled: bool = False
    news_sentiment_tg_alert_min_abs_value: float = 0.6  # |blended directional value| gate
    news_sentiment_tg_alert_dedup_ttl_seconds: int = 21_600  # fire once per direction per 6h
    # Score FinBERT in a spawned child process that exits after each call, so the long-lived
    # monitoring worker never imports torch. Railway bills GB-minutes, and torch cannot be released
    # in-process: measured 2026-09-15, dropping the pipeline recovered 89 of 472 MB under
    # linux/amd64 and prod stayed flat (x1.01). Cost: one spawn + torch import + model load per
    # scoring call (6.6 s measured locally). Set false to score in-process again.
    headline_sentiment_finbert_in_child_process: bool = True
    # If RSS yields no headlines, optionally merge texts from headline_sentiment_seed.yaml (default off).
    headline_sentiment_emergency_seed_fallback: bool = False
    # Per-IP ceiling for the public market/config/funding reads that carried NO limit at all
    # (config.public x2, funding_backtest, funding_monitor, funding_paper, market_insights).
    # MEASURED 2026-09-15 on http://127.0.0.1:3000/en/chart, anonymous: a whole page load is 16
    # API calls in a ~10s burst and then 0/min, and it touches each of these routes at most twice.
    # 120/min is therefore ~60 page loads a minute from ONE IP -- unreachable for a human, and for
    # shared egress (office NAT, mobile CGNAT) it still allows dozens of simultaneous readers,
    # while a scraper looping funding data hits it in seconds.
    public_market_data_rate_limit_per_minute: int = 120
    headline_rss_timeout_seconds: float = 15.0
    headline_rss_max_response_bytes: int = 2_000_000
    # RSS items published longer ago than this are never scored as current news. HTTP 200 does not
    # mean a feed is alive: measured 2026-09-15, WSJ Markets (feeds.a.dj.com) answered 200 with 20
    # items, the newest 596 days old, and 4 of them were ingested on every refresh. 72h spans a
    # weekend (Friday close -> Monday open) so slow-weekend feeds are not emptied.
    headline_rss_max_entry_age_hours: float = 72.0
    # Cap total headlines per ingest across all curated feeds. Measured 2026-08-25:
    # sum(headline_max_items) across 36 ingesting feeds = 96; keeping this BELOW that
    # silently drops later-sorted sources (crypto / Investing macro RSS). FinBERT scores
    # are per-headline Redis-cached (6h), so raising this is mostly first-miss CPU, not
    # steady-state cost — DeepSeek stays capped separately at NEWS_IMPACT_MAX_HEADLINES_PER_CYCLE.
    headline_ingestion_global_max_items: int = 120
    headline_rss_user_agent: str = "PulsAI-HeadlineBot/1.0 (+https://pulsai.live)"
    # Max concurrent WebSocket /ws/signal connections per client IP (abuse guard).
    websocket_max_connections_per_ip: int = 30
    websocket_reconnect_max_retries: int = 10
    websocket_reconnect_base_delay: float = 1.0
    websocket_reconnect_max_delay: float = 60.0

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # Keys only in API/worker env — never browser / NEXT_PUBLIC_*.
    # Spike endpoint prefers CryptoQuant when CRYPTOQUANT_ACCESS_TOKEN is set, else Glassnode.

    glassnode_api_key: str = ""
    glassnode_base_url: str = "https://api.glassnode.com"
    glassnode_request_timeout_seconds: float = 15.0

    cryptoquant_access_token: str = ""
    cryptoquant_base_url: str = "https://api.cryptoquant.com"
    cryptoquant_request_timeout_seconds: float = 15.0

    # Coinglass v4 — derivatives OI / funding / liquidations / L/S (research + chart indicators).
    # Never expose to browser. Set COINGLASS_API_KEY in API/worker .env only.
    coinglass_api_key: str = ""
    coinglass_base_url: str = COINGLASS_DEFAULT_BASE_URL
    coinglass_request_timeout_seconds: float = 30.0

    # Coin Metrics — research A/B panel only (ReferenceRateUSD). Not production chart/execution SoT.
    # Set COINMETRICS_API_KEY in API/worker .env. Community tier is CC BY-NC; commercial needs paid license.
    coinmetrics_api_key: str = ""

    # Liquidation heatmap chart overlay — OI+leverage fallback when Coinglass Model3 unavailable.
    liquidation_heatmap_enable_oi_fallback: bool = True

    # Phase 4 B.1 — periodic Postgres snapshots for backtest replay (no lookahead).
    liquidation_heatmap_history_enabled: bool = True
    liquidation_heatmap_history_retention_days: int = 30

    # BGeometrics / bitcoin-data.com: free keyless MVRV+SOPR fallback for the on-chain
    # card when no Glassnode key. Toggle off to keep the honest "unavailable" placeholder.
    bgeometrics_base_url: str = "https://bitcoin-data.com"
    on_chain_free_fallback_enabled: bool = True
    fred_api_key: str = ""
    # When True (default), GET /sentiment/detailed runs a full macro Redis refresh if the cache is empty
    # (local dev without Celery). Set MACRO_SNAPSHOT_REFRESH_ON_CACHE_MISS=0 in production if you want
    # Celery-only updates only.
    macro_snapshot_refresh_on_cache_miss: bool = True
    # Trading Economics (calendar / consensus for economic surprise Tier 2). Optional; Tier 1 uses FRED only.
    trading_economics_api_key: str = ""
    te_api_timeout_seconds: float = 10.0

    # When True, spike returns deterministic stub (CI, local without keys). Never present as live vendor data.
    on_chain_use_stub: bool = False
    fundamental_onchain_spike_rate_limit_per_minute: int = 30

    # blockchain.com free, keyless on-chain fallback. When enabled (default), the auto
    # on-chain spike degrades to a free network-activity metric if Glassnode AND
    # CryptoQuant are unavailable (no key / failure), instead of 502/stub. It is a
    # DEGRADED proxy (not MVRV/SOPR/exchange-flow) — clearly labeled provider=blockchain.com.
    on_chain_blockchaincom_fallback_enabled: bool = True
    blockchaincom_base_url: str = "https://api.blockchain.info"
    blockchaincom_request_timeout_seconds: float = 15.0

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    local_external_notifications_enabled: bool = False
