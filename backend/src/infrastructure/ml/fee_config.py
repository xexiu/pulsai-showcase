"""
Fee configuration service for backtesting.

Single abstraction for spot trading fees. Default implementation returns
EXCHANGE_FEES (Binance/Bitget 0.1%). Future: per-user/VIP overrides, BNB discount.

WHY: Keeps backtester and endpoints agnostic of where fees come from;
extensibility (user_id, VIP tier, use_bnb_discount) without changing call sites.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.enums import Exchange
from src.shared.constants.fees import FeeSchedule

from .backtester_types import EXCHANGE_FEES, PERP_EXCHANGE_FEES, ExchangeFees


class FeeConfigService(Protocol):
    """Read-only interface for spot AND perpetual fee lookup."""

    def get_spot_fees(
        self,
        exchange: Exchange,
        user_id: UUID | None = None,
    ) -> ExchangeFees:
        """Return fee config for the given exchange (and optionally user)."""
        ...

    def get_perp_fees(
        self,
        exchange: Exchange,
        user_id: UUID | None = None,
    ) -> ExchangeFees:
        """Return PERPETUAL (futures) fee config — not the spot rate."""
        ...


class DefaultFeeConfigService:
    """
    Default fee config: returns EXCHANGE_FEES[exchange].

    user_id is ignored today; reserved for future per-user/VIP overrides.
    """

    def get_spot_fees(
        self,
        exchange: Exchange,
        user_id: UUID | None = None,
    ) -> ExchangeFees:
        """
        Return spot fees for exchange.

        When user_id is None or no override exists, returns EXCHANGE_FEES[exchange].
        Future: lookup user tier, BNB discount, etc.
        """
        del user_id  # reserved for per-user/VIP overrides; discarded explicitly, not ignored
        return EXCHANGE_FEES.get(exchange, EXCHANGE_FEES[Exchange.BINANCE])

    def get_perp_fees(
        self,
        exchange: Exchange,
        user_id: UUID | None = None,
    ) -> ExchangeFees:
        """Return PERPETUAL fees for exchange.

        A leveraged lane is a futures trade and is priced like one. Verified 2026-09-21 against
        the venues' published standard-tier schedules: Binance USDⓈ-M 0.020% maker / 0.050% taker,
        Bitget USDT-M 0.020% / 0.060%, BloFin 0.0200% / 0.0600% — versus 0.10% a leg on spot.
        """
        del user_id  # reserved for per-user/VIP overrides; discarded explicitly, not ignored
        return PERP_EXCHANGE_FEES.get(exchange, PERP_EXCHANGE_FEES[Exchange.BINANCE])


# Singleton for dependency injection; callers can use this or pass their own.
default_fee_config_service: FeeConfigService = DefaultFeeConfigService()


class ZeroFeeConfigService:
    """The ``zero`` schedule (ADR-029 Decision 1, amended 2026-09-30): the owner's MEXC VIP cost.

    Maker, taker AND slippage are 0 (owner, 2026-09-28: "0% FEES cause im vip on mexc!!! slippage 0"). The
    standard 0.03 %/side slippage is an unmeasured default -- 6 bps a round trip -- while the measured MEXC
    market-order round trip at $50k is 0.012 bps on BTC and 0.037 on ETH (pine/mexc_book_cost.py); on a 5m book
    earning ~1.5 bps a trade it decided every verdict. A measured book cost is a labelled sensitivity, never this.
    """

    def __init__(self, standard: FeeConfigService = default_fee_config_service) -> None:
        self._standard = standard

    def get_spot_fees(self, exchange: Exchange, user_id: UUID | None = None) -> ExchangeFees:
        """Spot fees with maker, taker and slippage waived."""
        return _waived(self._standard.get_spot_fees(exchange, user_id))

    def get_perp_fees(self, exchange: Exchange, user_id: UUID | None = None) -> ExchangeFees:
        """Perpetual fees with maker, taker and slippage waived."""
        return _waived(self._standard.get_perp_fees(exchange, user_id))


def _waived(fees: ExchangeFees) -> ExchangeFees:
    return fees.model_copy(update={"maker_fee": 0.0, "taker_fee": 0.0, "slippage": 0.0})


_SERVICE_BY_SCHEDULE: dict[FeeSchedule, FeeConfigService] = {
    FeeSchedule.STANDARD: default_fee_config_service,
    FeeSchedule.ZERO: ZeroFeeConfigService(),
}


def fee_config_service_for(schedule: FeeSchedule) -> FeeConfigService:
    """The service that charges ``schedule`` -- the cert engine's one fee switch (``_run_cell``)."""
    return _SERVICE_BY_SCHEDULE[schedule]
