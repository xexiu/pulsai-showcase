"""Settings mixin — Trading, Signal, Chart API (sections 12-14)."""

from typing import Literal

from pydantic import Field, computed_field

from src.shared.constants.confidence import DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT
from src.shared.constants.timeframes import (
    DEFAULT_SUPPORTED_TIMEFRAME_VALUES,
    DEFAULT_TIMEFRAME,
    get_supported_timeframes,
)
from src.shared.constants.trading import (
    DEFAULT_EXCHANGE,
    DEFAULT_SUPPORTED_SYMBOL_VALUES,
    DEFAULT_SYMBOL,
    SUPPORTED_EXCHANGE_VALUES,
    get_supported_exchanges,
)


class SettingsTradingMixin:
    # ═══════════════════════════════════════════════════════════════════════════
    # WHY: All trading-related defaults should be configurable, not hardcoded
    # in route handlers, services, or workers.

    default_symbol: str = DEFAULT_SYMBOL
    default_timeframe: str = DEFAULT_TIMEFRAME
    default_exchange: str = DEFAULT_EXCHANGE

    # Supported symbols and timeframes (comma-separated in .env)
    # Used for validation and UI dropdowns
    # NOTE: For production MVP, limit to BTC/USDT only via SUPPORTED_SYMBOLS env var
    supported_symbols: str = ",".join(DEFAULT_SUPPORTED_SYMBOL_VALUES)
    # Exact symbol allowlist for free-tier/anonymous trading access (comma-separated).
    # WHY explicit list:
    # - Product can pin free tier to specific symbols without relying on symbol order.
    # - Frontend and backend consume the same policy from /config/public.
    free_tier_allowed_symbols: str = "BTC/USDT"
    # Must match TIMEFRAME_CONFIGS in domain/services/features/timeframe_indicator_configs.py.
    supported_timeframes: str = ",".join(DEFAULT_SUPPORTED_TIMEFRAME_VALUES)
    supported_exchanges: str = ",".join(SUPPORTED_EXCHANGE_VALUES)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def supported_symbols_list(self) -> list[str]:
        """Parse supported symbols from comma-separated string."""
        return [s.strip() for s in self.supported_symbols.split(",") if s.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def free_tier_allowed_symbols_list(self) -> list[str]:
        """Parse and validate free-tier symbol allowlist against supported symbols."""
        configured = [s.strip() for s in self.free_tier_allowed_symbols.split(",") if s.strip()]
        allowed = set(self.supported_symbols_list)
        invalid = [s for s in configured if s not in allowed]
        if invalid:
            raise ValueError("Unsupported free-tier symbols: " + ", ".join(invalid) + f". Allowed: {self.supported_symbols_list}")
        if not configured:
            raise ValueError("free_tier_allowed_symbols must include at least one symbol")
        return configured

    @computed_field  # type: ignore[prop-decorator]
    @property
    def supported_timeframes_list(self) -> list[str]:
        """Return configured timeframes as a validated subset of the backend registry."""
        return get_supported_timeframes(self.supported_timeframes)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def supported_exchanges_list(self) -> list[str]:
        """Return configured exchanges as a validated subset of the backend registry."""
        return get_supported_exchanges(self.supported_exchanges)

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    enable_live_signals: bool = True
    # When True, emit JSON lines on logger ``live_signal.trace`` (Celery OHLCV tier, ML timings, TG).
    live_signal_trace_logging: bool = Field(
        default=False,
        description="Structured live pipeline logs (env LIVE_SIGNAL_TRACE_LOGGING)",
    )
    # When True, Binance OHLCV stream supervisor uses raw ``@kline`` WS (``k.x``) instead of CCXT Pro watch_ohlcv.
    binance_ohlcv_kline_fastpath: bool = Field(
        default=False,
        description="Binance kline finalize fast-path for stream supervisor (env BINANCE_OHLCV_KLINE_FASTPATH)",
    )
    # When True, fetch last N+B closed bars then narrow with build_live_contract_slice (same LIVE_STEP as admin tools).
    live_signal_wide_fetch_then_live_step_slice: bool = Field(
        default=False,
        description="Wide OHLCV fetch then LIVE_STEP narrow (env LIVE_SIGNAL_WIDE_FETCH_THEN_LIVE_STEP_SLICE)",
    )
    live_signal_wide_fetch_buffer_bars: int = Field(
        default=64,
        ge=0,
        le=500,
        description="Extra closed bars beyond live tail N when wide fetch is on (env LIVE_SIGNAL_WIDE_FETCH_BUFFER_BARS)",
    )
    # IANA id for Celery-persisted candle local ISO times when no user/request override.
    signal_display_timezone_default: str = Field(
        default="UTC",
        description="Default display timezone for signal candle_open/close_local_iso (env SIGNAL_DISPLAY_TIMEZONE_DEFAULT)",
    )
    # When True, POST /api/v1/signals/generate returns 401 without a valid session (env SIGNALS_GENERATE_REQUIRE_AUTHENTICATION).
    signals_generate_require_authentication: bool = Field(
        default=False,
        description="Require authentication for on-demand signal generation (default off for curl/smoke tools)",
    )
    # SoT percent (0-100) for UI + public config; env SIGNAL_MIN_CONFIDENCE_PERCENT
    signal_min_confidence_percent: int = DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT

    # Fired sources computation/payload policy.
    # always: always compute fired sources in signal generation.
    # conditional: compute only when at least one enabled channel requires it.
    # never: never compute fired sources.
    compute_fired_sources_mode: Literal["always", "conditional", "never"] = "always"
    include_fired_sources_in_api: bool = True
    include_fired_sources_in_ws: bool = True
    include_fired_sources_in_telegram: bool = True

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # Default for GET /market/ohlcv and GET /market/chart-indicators when client
    # does not send include_current_candle. False = closed candles only; True = last
    # bar is the current (forming) candle. FE chart pages pass true explicitly.

    chart_include_current_candle_default: bool = False

    # ═══════════════════════════════════════════════════════════════════════════
