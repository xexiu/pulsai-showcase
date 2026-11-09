"""FSM: automation status transitions."""

from __future__ import annotations

import pytest

from src.domain.services.trading_automation_status import validate_automation_status_transition
from src.shared.constants.trading_automation import TradingAutomationStatus
from src.shared.exceptions import ValidationError


def test_draft_to_active_allowed() -> None:
    validate_automation_status_transition(
        TradingAutomationStatus.DRAFT.value,
        TradingAutomationStatus.ACTIVE.value,
    )


def test_active_to_paused_and_back() -> None:
    validate_automation_status_transition(
        TradingAutomationStatus.ACTIVE.value,
        TradingAutomationStatus.PAUSED.value,
    )
    validate_automation_status_transition(
        TradingAutomationStatus.PAUSED.value,
        TradingAutomationStatus.ACTIVE.value,
    )


def test_killed_is_terminal() -> None:
    with pytest.raises(ValidationError):
        validate_automation_status_transition(
            TradingAutomationStatus.KILLED.value,
            TradingAutomationStatus.ACTIVE.value,
        )
