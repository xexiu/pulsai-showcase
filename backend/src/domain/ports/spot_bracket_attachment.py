"""Port: venue-specific spot SL/TP attachment (plan / conditional), not swap presets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

SpotBracketScheduleKind = Literal["supported", "unsupported", "deferred"]


@dataclass(frozen=True, slots=True)
class SpotBracketScheduleOutcome:
    """Result of evaluating whether spot brackets may be attached for a venue."""

    kind: SpotBracketScheduleKind
    """supported: user may send SL/TP with spot; unsupported: reject at policy edge."""

    code: str | None
    """Stable machine code when ``kind == unsupported`` (see ``spot_bracket_errors``)."""


@runtime_checkable
class SpotBracketAttachmentStrategy(Protocol):
    """Exchange-specific spot bracket attachment (separate from swap preset SL/TP)."""

    def supports_spot_plan_brackets(self) -> bool:
        """True when paper/live spot orders may include ``stop_loss`` / ``take_profit`` prices."""
        ...

    def schedule_outcome_preview(self) -> SpotBracketScheduleOutcome:
        """Outcome used by policy layer before order submission (no I/O)."""
        ...


class UnsupportedSpotBracketStrategy:
    """Default: no spot plan brackets for this venue."""

    def supports_spot_plan_brackets(self) -> bool:
        return False

    def schedule_outcome_preview(self) -> SpotBracketScheduleOutcome:
        from src.shared.constants.spot_bracket_errors import SPOT_BRACKET_UNSUPPORTED_VENUE

        return SpotBracketScheduleOutcome(kind="unsupported", code=SPOT_BRACKET_UNSUPPORTED_VENUE)


class NotImplementedSpotBracketStrategy:
    """Registered slot reserved for a venue whose strategy is not wired yet."""

    def supports_spot_plan_brackets(self) -> bool:
        return False

    def schedule_outcome_preview(self) -> SpotBracketScheduleOutcome:
        from src.shared.constants.spot_bracket_errors import SPOT_BRACKET_NOT_IMPLEMENTED

        return SpotBracketScheduleOutcome(kind="unsupported", code=SPOT_BRACKET_NOT_IMPLEMENTED)


__all__ = [
    "NotImplementedSpotBracketStrategy",
    "SpotBracketAttachmentStrategy",
    "SpotBracketScheduleOutcome",
    "UnsupportedSpotBracketStrategy",
]
