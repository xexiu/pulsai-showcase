"""Unit tests for the Binance OHLCV source SoT constants + resolvers.

Covers:
- Source list ordering (direct-first, proxy-last).
- Proxy dedup when proxy is already a Binance host.
- assert_binance_only_sources raises on non-Binance hosts.
- assert_binance_only_sources allows the configured trusted proxy.
- Env resolvers: default values, custom valid values, invalid/garbage fallback.
- _resolve_positive_float: default, valid, invalid, zero, negative.
- Redis key builder output.
"""

from __future__ import annotations

import pytest

from src.shared.constants.ohlcv_sources import (
    ALL_DOWN_ALERT_KEY,
    ALLOWED_BINANCE_HOST_SUFFIXES,
    BINANCE_OHLCV_FAILOVER_ENABLED_ENV_VAR,
    BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS_ENV_VAR,
    BINANCE_OHLCV_PROBE_CONFIRM_DELAY_ENV_VAR,
    BINANCE_OHLCV_PROBE_TIMEOUT_ENV_VAR,
    BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_ENV_VAR,
    BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR,
    BINANCE_SPOT_API,
    DATA_API_BINANCE_VISION,
    DEFAULT_BINANCE_OHLCV_FAILOVER_ENABLED,
    DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS,
    DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS,
    DEFAULT_BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS,
    DEFAULT_BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS,
    DEFAULT_BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS,
    SOURCE_PROBE_PATH,
    assert_binance_only_sources,
    breaker_alert_key,
    breaker_gate_key,
    resolve_binance_ohlcv_failover_enabled,
    resolve_binance_ohlcv_probe_confirm_attempts,
    resolve_binance_ohlcv_probe_confirm_delay_seconds,
    resolve_binance_ohlcv_probe_timeout_seconds,
    resolve_binance_ohlcv_source_alert_cooldown_seconds,
    resolve_binance_ohlcv_source_cooldown_seconds,
    resolve_binance_ohlcv_sources,
)

# ---------------------------------------------------------------------------
# Constants smoke tests
# ---------------------------------------------------------------------------


def test_data_api_binance_vision_value() -> None:
    assert DATA_API_BINANCE_VISION == "https://data-api.binance.vision"


def test_binance_spot_api_value() -> None:
    assert BINANCE_SPOT_API == "https://api.binance.com"


def test_source_probe_path_value() -> None:
    assert SOURCE_PROBE_PATH == "/api/v3/time"


def test_allowed_binance_host_suffixes_contains_required_hosts() -> None:
    required = {
        "data-api.binance.vision",
        "api.binance.com",
        "api1.binance.com",
        "api2.binance.com",
        "api3.binance.com",
        "api4.binance.com",
        "api-gcp.binance.com",
    }
    assert required <= ALLOWED_BINANCE_HOST_SUFFIXES


def test_default_failover_enabled_is_false() -> None:
    assert DEFAULT_BINANCE_OHLCV_FAILOVER_ENABLED is False


def test_default_cooldowns_and_timeout() -> None:
    assert DEFAULT_BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS == 120
    assert DEFAULT_BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS == 900
    assert DEFAULT_BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS == 3.0
    assert DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS == 2
    assert DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS == 0.5


def test_all_down_alert_key_stable() -> None:
    assert ALL_DOWN_ALERT_KEY == "ohlcv:source:alert:all_down"


# ---------------------------------------------------------------------------
# Source list ordering
# ---------------------------------------------------------------------------


def test_source_list_direct_first_no_proxy() -> None:
    """With empty proxy, list = [api.binance.com, data-api.binance.vision].

    api.binance.com is FIRST because it serves the full ccxt surface
    (load_markets/futures); .vision is a public-data-only klines fallback.
    """
    sources = resolve_binance_ohlcv_sources("")
    assert sources == [BINANCE_SPOT_API, DATA_API_BINANCE_VISION]


def test_source_list_proxy_appended_last() -> None:
    """A non-Binance-listed proxy is appended after the direct hosts."""
    proxy = "https://my-cf-worker.example.com"
    sources = resolve_binance_ohlcv_sources(proxy)
    assert sources[0] == BINANCE_SPOT_API
    assert sources[1] == DATA_API_BINANCE_VISION
    assert sources[2] == proxy
    assert len(sources) == 3


def test_source_list_direct_first_invariant() -> None:
    """Direct Binance hosts always precede the proxy in the resolved list."""
    proxy = "https://proxy.example.org"
    sources = resolve_binance_ohlcv_sources(proxy)
    direct_indices = [sources.index(DATA_API_BINANCE_VISION), sources.index(BINANCE_SPOT_API)]
    proxy_index = sources.index(proxy)
    assert all(i < proxy_index for i in direct_indices)


def test_source_list_dedup_when_proxy_is_binance_spot_api() -> None:
    """When proxy == api.binance.com, it is NOT duplicated in the list."""
    sources = resolve_binance_ohlcv_sources(BINANCE_SPOT_API)
    assert sources.count(BINANCE_SPOT_API) == 1
    assert len(sources) == 2  # Only the two direct hosts.


def test_source_list_dedup_when_proxy_is_data_api() -> None:
    """When proxy == data-api.binance.vision, it is NOT duplicated."""
    sources = resolve_binance_ohlcv_sources(DATA_API_BINANCE_VISION)
    assert sources.count(DATA_API_BINANCE_VISION) == 1
    assert len(sources) == 2


def test_source_list_trailing_slash_normalized() -> None:
    """Trailing slash on proxy is stripped before dedup."""
    # api.binance.com/ should deduplicate against https://api.binance.com
    sources = resolve_binance_ohlcv_sources(BINANCE_SPOT_API + "/")
    assert len(sources) == 2


# ---------------------------------------------------------------------------
# assert_binance_only_sources — must raise on non-Binance hosts
# ---------------------------------------------------------------------------


def test_assert_raises_on_coinbase() -> None:
    """https://api.coinbase.com must be rejected (non-Binance exchange)."""
    with pytest.raises(ValueError, match="coinbase"):
        assert_binance_only_sources(
            ["https://api.coinbase.com"],
            trusted_proxy="",
        )


def test_assert_raises_on_kraken() -> None:
    """A Kraken-style URL must be rejected."""
    with pytest.raises(ValueError, match="kraken"):
        assert_binance_only_sources(
            ["https://api.kraken.com/0/public"],
            trusted_proxy="",
        )


def test_assert_raises_on_bybit() -> None:
    """A Bybit host must be rejected."""
    with pytest.raises(ValueError, match="bybit"):
        assert_binance_only_sources(
            [DATA_API_BINANCE_VISION, "https://api.bybit.com"],
            trusted_proxy="",
        )


def test_assert_error_message_mentions_model_parity() -> None:
    """The ValueError message should mention model/candle parity so it is actionable."""
    with pytest.raises(ValueError, match="Binance candles"):
        assert_binance_only_sources(
            ["https://api.coinbase.com"],
            trusted_proxy="",
        )


def test_assert_allows_trusted_proxy() -> None:
    """The trusted proxy is always allowed, even if not a Binance host."""
    proxy = "https://my-cf-worker.example.com"
    # Should not raise.
    assert_binance_only_sources([DATA_API_BINANCE_VISION, proxy], trusted_proxy=proxy)


def test_assert_allows_all_known_binance_hosts() -> None:
    """All seven ALLOWED_BINANCE_HOST_SUFFIXES should pass without exception."""
    urls = [f"https://{suffix}" for suffix in ALLOWED_BINANCE_HOST_SUFFIXES]
    # Should not raise.
    assert_binance_only_sources(urls, trusted_proxy="")


def test_assert_raises_names_offending_url() -> None:
    """The error message includes the offending URL for debuggability."""
    bad_url = "https://api.coinbase.com"
    with pytest.raises(ValueError, match=bad_url):
        assert_binance_only_sources([bad_url], trusted_proxy="")


# ---------------------------------------------------------------------------
# resolve_binance_ohlcv_failover_enabled
# ---------------------------------------------------------------------------


class TestResolveFailoverEnabled:
    def test_default_when_missing(self) -> None:
        assert resolve_binance_ohlcv_failover_enabled({}) is False

    @pytest.mark.parametrize("token", ["1", "true", "TRUE", "yes", "On"])
    def test_truthy_tokens(self, token: str) -> None:
        assert resolve_binance_ohlcv_failover_enabled({BINANCE_OHLCV_FAILOVER_ENABLED_ENV_VAR: token}) is True

    @pytest.mark.parametrize("token", ["0", "false", "no", "OFF"])
    def test_falsy_tokens(self, token: str) -> None:
        assert resolve_binance_ohlcv_failover_enabled({BINANCE_OHLCV_FAILOVER_ENABLED_ENV_VAR: token}) is False

    def test_garbage_falls_back_to_false(self) -> None:
        assert resolve_binance_ohlcv_failover_enabled({BINANCE_OHLCV_FAILOVER_ENABLED_ENV_VAR: "maybe"}) is False


# ---------------------------------------------------------------------------
# resolve_binance_ohlcv_source_cooldown_seconds
# ---------------------------------------------------------------------------


class TestResolveCooldown:
    def test_default_when_missing(self) -> None:
        assert resolve_binance_ohlcv_source_cooldown_seconds({}) == DEFAULT_BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS

    def test_custom_valid(self) -> None:
        assert resolve_binance_ohlcv_source_cooldown_seconds({BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR: "60"}) == 60

    @pytest.mark.parametrize("bad", ["0", "-1", "abc", ""])
    def test_invalid_falls_back_to_default(self, bad: str) -> None:
        assert (
            resolve_binance_ohlcv_source_cooldown_seconds({BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR: bad})
            == DEFAULT_BINANCE_OHLCV_SOURCE_COOLDOWN_SECONDS
        )


# ---------------------------------------------------------------------------
# resolve_binance_ohlcv_source_alert_cooldown_seconds
# ---------------------------------------------------------------------------


class TestResolveAlertCooldown:
    def test_default_when_missing(self) -> None:
        assert resolve_binance_ohlcv_source_alert_cooldown_seconds({}) == DEFAULT_BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS

    def test_custom_valid(self) -> None:
        assert resolve_binance_ohlcv_source_alert_cooldown_seconds({BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_ENV_VAR: "300"}) == 300

    @pytest.mark.parametrize("bad", ["-100", "0", "nope"])
    def test_invalid_falls_back_to_default(self, bad: str) -> None:
        assert (
            resolve_binance_ohlcv_source_alert_cooldown_seconds({BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_ENV_VAR: bad})
            == DEFAULT_BINANCE_OHLCV_SOURCE_ALERT_COOLDOWN_SECONDS
        )


# ---------------------------------------------------------------------------
# resolve_binance_ohlcv_probe_timeout_seconds (_resolve_positive_float)
# ---------------------------------------------------------------------------


class TestResolveProbeTimeout:
    def test_default_when_missing(self) -> None:
        result = resolve_binance_ohlcv_probe_timeout_seconds({})
        assert result == DEFAULT_BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS

    def test_custom_valid_float(self) -> None:
        assert resolve_binance_ohlcv_probe_timeout_seconds({BINANCE_OHLCV_PROBE_TIMEOUT_ENV_VAR: "1.5"}) == 1.5

    def test_custom_valid_int_string(self) -> None:
        assert resolve_binance_ohlcv_probe_timeout_seconds({BINANCE_OHLCV_PROBE_TIMEOUT_ENV_VAR: "5"}) == 5.0

    @pytest.mark.parametrize("bad", ["0", "-1.0", "abc", "0.0", ""])
    def test_invalid_falls_back_to_default(self, bad: str) -> None:
        result = resolve_binance_ohlcv_probe_timeout_seconds({BINANCE_OHLCV_PROBE_TIMEOUT_ENV_VAR: bad})
        assert result == DEFAULT_BINANCE_OHLCV_PROBE_TIMEOUT_SECONDS

    def test_returns_float_type(self) -> None:
        result = resolve_binance_ohlcv_probe_timeout_seconds({})
        assert isinstance(result, float)


class TestResolveProbeConfirmAttempts:
    def test_default_when_missing(self) -> None:
        assert resolve_binance_ohlcv_probe_confirm_attempts({}) == DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS

    def test_custom_valid(self) -> None:
        assert resolve_binance_ohlcv_probe_confirm_attempts({BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS_ENV_VAR: "3"}) == 3

    @pytest.mark.parametrize("bad", ["0", "-1", "abc", ""])
    def test_invalid_falls_back(self, bad: str) -> None:
        assert (
            resolve_binance_ohlcv_probe_confirm_attempts({BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS_ENV_VAR: bad})
            == DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_ATTEMPTS
        )


class TestResolveProbeConfirmDelay:
    def test_default_when_missing(self) -> None:
        assert resolve_binance_ohlcv_probe_confirm_delay_seconds({}) == DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS

    def test_custom_valid(self) -> None:
        assert resolve_binance_ohlcv_probe_confirm_delay_seconds({BINANCE_OHLCV_PROBE_CONFIRM_DELAY_ENV_VAR: "0.25"}) == 0.25

    def test_zero_allowed(self) -> None:
        assert resolve_binance_ohlcv_probe_confirm_delay_seconds({BINANCE_OHLCV_PROBE_CONFIRM_DELAY_ENV_VAR: "0"}) == 0.0

    @pytest.mark.parametrize("bad", ["-1", "abc", ""])
    def test_invalid_falls_back(self, bad: str) -> None:
        assert (
            resolve_binance_ohlcv_probe_confirm_delay_seconds({BINANCE_OHLCV_PROBE_CONFIRM_DELAY_ENV_VAR: bad})
            == DEFAULT_BINANCE_OHLCV_PROBE_CONFIRM_DELAY_SECONDS
        )


# ---------------------------------------------------------------------------
# Redis key builders
# ---------------------------------------------------------------------------


def test_breaker_gate_key_format() -> None:
    key = breaker_gate_key("https://data-api.binance.vision")
    assert key == "ohlcv:source:breaker:data-api.binance.vision"


def test_breaker_gate_key_trailing_slash() -> None:
    key = breaker_gate_key("https://api.binance.com/")
    assert key == "ohlcv:source:breaker:api.binance.com"


def test_breaker_alert_key_format() -> None:
    key = breaker_alert_key("https://api.binance.com", "down")
    assert key == "ohlcv:source:alert:down:api.binance.com"


def test_breaker_alert_key_recovered_state() -> None:
    key = breaker_alert_key("https://data-api.binance.vision", "recovered")
    assert key == "ohlcv:source:alert:recovered:data-api.binance.vision"
