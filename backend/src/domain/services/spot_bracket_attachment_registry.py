"""Registry for :class:`SpotBracketAttachmentStrategy` (spot market type only)."""

from __future__ import annotations

from src.domain.ports.spot_bracket_attachment import (
    SpotBracketAttachmentStrategy,
    UnsupportedSpotBracketStrategy,
)
from src.shared.constants.exchanges import MARKET_TYPE_SPOT, MarketType

_DEFAULT_UNSUPPORTED = UnsupportedSpotBracketStrategy()


class SpotBracketAttachmentRegistry:
    """Resolve ``SpotBracketAttachmentStrategy`` by exchange id (spot only)."""

    def __init__(
        self,
        *,
        by_exchange_id: dict[str, SpotBracketAttachmentStrategy] | None = None,
    ) -> None:
        self._by_exchange_id: dict[str, SpotBracketAttachmentStrategy] = dict(by_exchange_id or {})

    def register(self, exchange_id: str, strategy: SpotBracketAttachmentStrategy) -> None:
        self._by_exchange_id[exchange_id.lower()] = strategy

    def resolve(self, *, exchange_id: str, market_type: MarketType) -> SpotBracketAttachmentStrategy:
        if market_type != MARKET_TYPE_SPOT:
            return _DEFAULT_UNSUPPORTED
        key = exchange_id.lower()
        return self._by_exchange_id.get(key, _DEFAULT_UNSUPPORTED)


__all__ = ["SpotBracketAttachmentRegistry"]
