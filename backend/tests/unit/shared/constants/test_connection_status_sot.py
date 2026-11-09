"""ConnectionStatus SoT regression: one definition in ``shared.constants.exchanges``.

Guards against re-introducing the three inline literals (``"active"``,
``"disconnected"``, ``"invalid"``) scattered across services/entities. All
lifecycle code MUST import the constants from here.
"""

from __future__ import annotations

from typing import Literal, get_args

from src.shared.constants.exchanges import (
    CONNECTION_STATUS_ACTIVE,
    CONNECTION_STATUS_DISCONNECTED,
    CONNECTION_STATUS_INVALID,
    ConnectionStatus,
)


def test_connection_status_literal_equals_string_constants() -> None:
    """Literal MUST enumerate exactly the three Final constants — no skew, no extras."""
    assert set(get_args(ConnectionStatus)) == {
        CONNECTION_STATUS_ACTIVE,
        CONNECTION_STATUS_DISCONNECTED,
        CONNECTION_STATUS_INVALID,
    }


def test_connection_status_string_constants_are_stable_lowercase() -> None:
    """Stability pin: DB column + API surface use lowercase string values."""
    assert CONNECTION_STATUS_ACTIVE == "active"
    assert CONNECTION_STATUS_DISCONNECTED == "disconnected"
    assert CONNECTION_STATUS_INVALID == "invalid"


def test_connection_status_alias_is_literal_triple() -> None:
    """ConnectionStatus is the canonical type for annotating connection.status column + DTOs."""
    assert ConnectionStatus == Literal["active", "disconnected", "invalid"]
