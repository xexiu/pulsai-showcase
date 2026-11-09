"""SoT for committed OHLCV test fixtures (recorded exchange candles, CI-safe loads)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from src.shared.constants.ml_inference_parity_fixtures import ML_INFERENCE_PARITY_FEATURE_COLUMNS
from src.shared.constants.timeframes import ALIGNMENT_TIMEFRAMES_ORDER, BANDED_TIMEFRAMES_ORDER

# JSON schema generation for files under ``tests/fixtures/ohlcv/``.
OHLCV_TEST_FIXTURE_SCHEMA_VERSION: Final[str] = "v1"

# Default row count when recording via ``scripts/record_ohlcv_fixture.py``.
OHLCV_TEST_FIXTURE_DEFAULT_RECORD_LIMIT: Final[int] = 500

# Canonical symbol for alignment-TF matrix (Binance spot).
OHLCV_TEST_FIXTURE_DEFAULT_SYMBOL: Final[str] = "BTC/USDT"

# Relative to ``apps/api`` root.
OHLCV_TEST_FIXTURE_RELATIVE_DIR: Final[str] = "tests/fixtures/ohlcv"

# Feature columns fingerprinted at record time (chart-surface subset; no network in CI).
OHLCV_TEST_FIXTURE_FEATURE_SNAPSHOT_COLUMNS: Final[tuple[str, ...]] = (
    "rsi_14",
    "gr_zone",
    "macd",
    "bb_upper",
    "bb_lower",
)

# Model inference columns (pinned mini-ML bundle SoT; Phase 2 fingerprints).
OHLCV_TEST_FIXTURE_MODEL_FEATURE_COLUMNS: Final[tuple[str, ...]] = ML_INFERENCE_PARITY_FEATURE_COLUMNS


class OhlcvFixtureSnapshotMode(StrEnum):
    """Which fingerprint blocks ``record_ohlcv_fixture.py`` writes."""

    CHART = "chart"
    MODEL = "model"
    BOTH = "both"


# Tail length for per-column fingerprints (stability vs sensitivity tradeoff).
OHLCV_TEST_FIXTURE_FINGERPRINT_TAIL_ROWS: Final[int] = 50

# Minimum rows required after feature calc (warmup guard for integration tests).
OHLCV_TEST_FIXTURE_MIN_POST_CALC_ROWS: Final[int] = 100

# Backward-compatible alias (prefer ``build_ohlcv_fixture_id`` for new ids).
OHLCV_TEST_FIXTURE_BTC_USDT_1H_500: Final[str] = "btc_usdt_1h_500"


def build_ohlcv_fixture_id(*, symbol: str, timeframe: str, limit: int) -> str:
    """SoT id shape: ``btc_usdt_{timeframe}_{limit}`` (symbol slash → underscore)."""
    slug = symbol.replace("/", "_").lower()
    return f"{slug}_{timeframe}_{limit}"


@dataclass(frozen=True, slots=True)
class OhlcvAlignmentFixtureSpec:
    """One alignment-TF recorded slice (see ``ALIGNMENT_TIMEFRAMES_ORDER``)."""

    fixture_id: str
    symbol: str
    timeframe: str
    limit: int


def alignment_ohlcv_fixture_specs(
    *,
    symbol: str = OHLCV_TEST_FIXTURE_DEFAULT_SYMBOL,
    limit: int = OHLCV_TEST_FIXTURE_DEFAULT_RECORD_LIMIT,
    timeframes: tuple[str, ...] = ALIGNMENT_TIMEFRAMES_ORDER,
) -> tuple[OhlcvAlignmentFixtureSpec, ...]:
    """Build the CI-required OHLCV fixture matrix (default: the signal-alignment timeframes)."""
    return tuple(
        OhlcvAlignmentFixtureSpec(
            fixture_id=build_ohlcv_fixture_id(symbol=symbol, timeframe=tf, limit=limit),
            symbol=symbol,
            timeframe=tf,
            limit=limit,
        )
        for tf in timeframes
    )


OHLCV_TEST_FIXTURE_ALIGNMENT_SPECS: Final[tuple[OhlcvAlignmentFixtureSpec, ...]] = alignment_ohlcv_fixture_specs()

OHLCV_TEST_FIXTURE_CANONICAL_IDS: Final[tuple[str, ...]] = tuple(spec.fixture_id for spec in OHLCV_TEST_FIXTURE_ALIGNMENT_SPECS)

#: Banded timeframes prod does NOT serve (1m since 2026-10-11). Trainable, so CI pins their feature
#: path on recorded bars too -- but they are not alignment fixtures: the cron never watches them and
#: the pinned-inference expectations cover only served timeframes. Record one with
#: ``scripts/record_ohlcv_fixture.py --timeframe <tf>``.
OHLCV_TEST_FIXTURE_TRAINING_ONLY_SPECS: Final[tuple[OhlcvAlignmentFixtureSpec, ...]] = alignment_ohlcv_fixture_specs(
    timeframes=tuple(tf for tf in BANDED_TIMEFRAMES_ORDER if tf not in ALIGNMENT_TIMEFRAMES_ORDER),
)

#: Every recorded OHLCV slice CI requires, alignment first.
OHLCV_TEST_FIXTURE_RECORDED_SPECS: Final[tuple[OhlcvAlignmentFixtureSpec, ...]] = (
    *OHLCV_TEST_FIXTURE_ALIGNMENT_SPECS,
    *OHLCV_TEST_FIXTURE_TRAINING_ONLY_SPECS,
)
