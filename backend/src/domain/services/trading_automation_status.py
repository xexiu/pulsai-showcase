"""
TradingAutomation status transitions (finite state machine).
"""

from __future__ import annotations

from src.shared.constants.trading_automation import TradingAutomationStatus
from src.shared.exceptions import ValidationError

_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    TradingAutomationStatus.DRAFT.value: frozenset(
        {
            TradingAutomationStatus.ACTIVE.value,
            TradingAutomationStatus.KILLED.value,
        },
    ),
    TradingAutomationStatus.ACTIVE.value: frozenset(
        {
            TradingAutomationStatus.PAUSED.value,
            TradingAutomationStatus.KILLED.value,
        },
    ),
    TradingAutomationStatus.PAUSED.value: frozenset(
        {
            TradingAutomationStatus.ACTIVE.value,
            TradingAutomationStatus.KILLED.value,
        },
    ),
    TradingAutomationStatus.KILLED.value: frozenset(),
}


def validate_automation_status_transition(current_status: str, new_status: str) -> None:
    """Raise ValidationError when ``new_status`` is not allowed from ``current_status``."""
    if current_status == new_status:
        return
    allowed = _VALID_TRANSITIONS.get(current_status, frozenset())
    if new_status not in allowed:
        raise ValidationError(
            message="Invalid automation status transition.",
            details={"current_status": current_status, "new_status": new_status},
        )
