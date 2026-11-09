"""Registry behavior for spot bracket attachment strategies."""

from __future__ import annotations

from src.domain.ports.spot_bracket_attachment import (
    SpotBracketScheduleOutcome,
    UnsupportedSpotBracketStrategy,
)
from src.domain.services.spot_bracket_attachment_registry import SpotBracketAttachmentRegistry
from src.shared.constants.exchanges import MARKET_TYPE_SPOT, MARKET_TYPE_SWAP


class _FakeSupportedStrategy:
    def supports_spot_plan_brackets(self) -> bool:
        return True

    def schedule_outcome_preview(self) -> SpotBracketScheduleOutcome:
        return SpotBracketScheduleOutcome(kind="supported", code=None)


def test_unknown_exchange_on_spot_returns_unsupported_singleton() -> None:
    reg = SpotBracketAttachmentRegistry()
    s = reg.resolve(exchange_id="kraken", market_type=MARKET_TYPE_SPOT)
    assert s.supports_spot_plan_brackets() is False
    out = s.schedule_outcome_preview()
    assert out.kind == "unsupported"
    assert out.code is not None


def test_registered_fake_strategy_supported() -> None:
    reg = SpotBracketAttachmentRegistry()
    reg.register("acme", _FakeSupportedStrategy())
    s = reg.resolve(exchange_id="ACME", market_type=MARKET_TYPE_SPOT)
    assert s.supports_spot_plan_brackets() is True


def test_resolve_is_case_insensitive_for_exchange_id() -> None:
    reg = SpotBracketAttachmentRegistry()
    reg.register("AcMe", _FakeSupportedStrategy())
    s = reg.resolve(exchange_id="acme", market_type=MARKET_TYPE_SPOT)
    assert s.supports_spot_plan_brackets() is True


def test_non_spot_market_always_unsupported_strategy() -> None:
    reg = SpotBracketAttachmentRegistry()
    reg.register("bitget", _FakeSupportedStrategy())
    s = reg.resolve(exchange_id="bitget", market_type=MARKET_TYPE_SWAP)
    assert isinstance(s, UnsupportedSpotBracketStrategy)
