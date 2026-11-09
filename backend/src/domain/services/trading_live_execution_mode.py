"""
Live-execution policy for the automation pipeline (Celery).

Manual /trade live trading is browser-direct (Tealstreet) and rejected at the
HTTP route layer; this module is read **only** by the automation executor to
resolve whether a given tick should hit mainnet CCXT or stay on testnet.

Two gates, both must pass:
  1. The connection row opted in via ``mainnet_execution_enabled=True``.
  2. The user passes the feature-flag gate
     (``feature_live_trading`` global, or
     ``feature_live_trading_internal_preview`` for admins on staging).

The partition predicate for ``paper_orders.ccxt_use_mainnet`` lives in
:mod:`src.domain.services.paper_orders_stats_partition` so stats reads can
import it without dragging in the policy gate.
"""

from __future__ import annotations

from src.domain.enums import STAFF_ROLES
from src.shared.constants.paper_trading import TRADING_MODE_LIVE, TRADING_MODE_PAPER


def user_may_use_live_trading(
    role: str,
    *,
    live_trading_enabled: bool,
    live_trading_internal_preview: bool,
) -> bool:
    """Public ``feature_live_trading`` or staging internal preview for staff.

    Takes the ROLE, not a user object. It previously took a ``_UserWithRole`` Protocol whose
    entire content was ``role: str`` -- which basedpyright could never satisfy with the ORM
    ``User`` (protocol matching compares the class-level ``Mapped[str]``, even though instance
    access resolves to plain ``str``). Passing the one value it reads removes the Protocol, the
    type error, and the reason to hand a whole ORM entity to a domain policy.
    """
    if live_trading_enabled:
        return True
    return live_trading_internal_preview and role in STAFF_ROLES


def resolve_automation_ccxt_execution_mode(
    role: str,
    *,
    connection_mainnet_opt_in: bool,
    live_trading_enabled: bool,
    live_trading_internal_preview: bool,
) -> str:
    """Return ``TRADING_MODE_LIVE`` when the row is opted-in AND the user passes the gate."""
    if not connection_mainnet_opt_in:
        return str(TRADING_MODE_PAPER)
    if not user_may_use_live_trading(
        role,
        live_trading_enabled=live_trading_enabled,
        live_trading_internal_preview=live_trading_internal_preview,
    ):
        return str(TRADING_MODE_PAPER)
    return str(TRADING_MODE_LIVE)
