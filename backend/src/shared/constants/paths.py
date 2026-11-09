"""
Path constants.

Default paths for model storage and other persistent data.

WHY centralize this?
- 9 places define Path("./models") independently
- Inconsistent paths could cause model loading failures
- Single source of truth for storage locations

@see docs/04-structural/CODING_STANDARDS.md - Section 2.0 DON'T REINVENT THE WHEEL
"""

from pathlib import Path
from typing import Final

# ============================================================================
# MODEL STORAGE
# ============================================================================

# Default path for trained ML models
# Structure: models/{safe_symbol}_{timeframe}/v{version}/
# e.g. BTC/USDT 1h, version 1 -> the btc_usdt_1h directory, v1, model.joblib
#
# WHY absolute apps/api path?
# - Workers, scripts, and CLI entry points can run with different cwd values
# - Relative defaults would point to different directories depending on caller
# - This keeps all backend entry points writing to the same model registry root
API_ROOT_PATH: Path = Path(__file__).resolve().parents[3]
DEFAULT_MODELS_PATH: Path = API_ROOT_PATH / "models"


# ============================================================================
# BACKTEST DATASET STORAGE (Initiative 2 - frozen, content-addressable OHLCV bundles)
# ============================================================================
# Materialized OHLCV bundles for reproducible backtests. Layout:
#   data/backtest_datasets/{dataset_id}.parquet  - immutable OHLCV bundle
#   data/backtest_datasets/{dataset_id}.json     - sidecar metadata
DEFAULT_BACKTEST_DATASETS_PATH: Path = API_ROOT_PATH / "data" / "backtest_datasets"

# A venue's closed bars, kept so a grade reads them before it asks the venue (infrastructure/exchange/bar_store):
#   data/venue_bars/{venue}_{coin}_{resolution}.parquet  - one unbroken run of closed bars, extended on each read
DEFAULT_VENUE_BARS_PATH: Path = API_ROOT_PATH / "data" / "venue_bars"
DEFAULT_GRADED_TRADES_PATH: Final = API_ROOT_PATH / "data" / "live" / "graded_trades"
DEFAULT_OPTION_CHAINS_PATH: Path = API_ROOT_PATH / "data" / "option_chains"

# A forecaster's fitted parameters, kept by their inputs' content (sol_v2_volatility_forecasts.arma_params, joblib.Memory):
#   data/fit_cache/joblib/...  - one entry per fit; a refit fitted once is never fitted again
DEFAULT_FIT_CACHE_PATH: Path = API_ROOT_PATH / "data" / "fit_cache"


# ============================================================================
# OFFLINE RESEARCH LAB (apps/api-relative) — the ONE spelling of "src/research"
# ============================================================================
# research_loop_paths.py (and its insights_tier_paths.py sibling) derive every one of their
# ~23 artifact-path constants from these two roots via f-string composition, so a future root
# move (e.g. caches -> var/research/) is a ONE-constant change here rather than a find-and-replace
# across every derived constant. See tests/unit/architecture/
# test_no_research_path_literal_outside_the_root_constant.py — this module is the only one
# `_ALLOWED_SOT_MODULES` permits to spell the root literally.
RESEARCH_ROOT_REL: Final[str] = "src/research"
ARTIFACT_ROOT_REL: Final[str] = f"{RESEARCH_ROOT_REL}/artifacts"
