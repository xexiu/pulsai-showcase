"""SoT for Coinglass derivatives-flow chart overlay (Phase 3 D.2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DERIVATIVES_FLOW_DEFAULT_LIMIT: Final[int] = 500
DERIVATIVES_FLOW_MAX_LIMIT: Final[int] = 2000
DERIVATIVES_FLOW_CACHE_TTL_S: Final[int] = 120

DERIVATIVES_FLOW_COARSER_INTERVAL_WARNING_TEMPLATE: Final[str] = (
    "Coinglass open interest and liquidation history are shown at "
    "{fetch_interval} resolution (chart timeframe {chart_timeframe} is not on the current API plan)."
)

COINGLASS_PLAN_INTERVAL_ERROR_TOKEN: Final[str] = "interval"

#: Periods Binance's public ``openInterestHist`` publishes; the chart's own timeframe must be one of
#: them for the open-interest fallback (it serves only the latest 30 days, at most 500 rows).
BINANCE_OPEN_INTEREST_PERIODS: Final[frozenset[str]] = frozenset({"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"})
BINANCE_OPEN_INTEREST_MAX_LIMIT: Final[int] = 500
#: A chart timeframe Binance does not publish, served from a finer period it does: the points on the
#: chart's own bar boundaries are kept (8h bars open at 00:00 / 08:00 / 16:00 UTC, all 4h boundaries).
BINANCE_OPEN_INTEREST_FINER_PERIOD: Final[dict[str, str]] = {"8h": "4h"}
DERIVATIVES_FLOW_BINANCE_FALLBACK_WARNING: Final[str] = (
    "Coinglass is unavailable: open interest is shown from Binance (latest 30 days); liquidation history needs Coinglass."
)


class DerivativesFlowSourceId(StrEnum):
    """Data source for OI + liquidation history series."""

    COINGLASS = "coinglass"
    #: Binance's public openInterestHist -- the fallback while Coinglass refuses (2026-10-03).
    BINANCE = "binance"


class DerivativesFlowQuality(StrEnum):
    """Chart overlay quality label (vendor vs unavailable)."""

    VENDOR = "vendor"
    UNAVAILABLE = "unavailable"
