"""
Compound v2: per-leg JSON schedule (swap) — leverage after anchor leg.

``compound_leg_schedule_v2`` is a JSON array of objects, one per **post-anchor** leg.
Leg ``n`` (1-based anchor = 1) uses schedule row index ``n - 2`` when ``n >= 2``:
``open_position_fill_count`` is the aggregate ``fill_count`` **before** placing the next order.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Final

from src.shared.exceptions import ValidationError

logger = logging.getLogger(__name__)


def normalize_compound_leg_schedule_v2(raw: Any) -> list[dict[str, Any]]:
    """Parse and validate ``compound_leg_schedule_v2`` from a strategy snapshot."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationError(
            message="compound_leg_schedule_v2 must be a JSON array.",
            details={"compound_leg_schedule_v2": "not_a_list"},
        )
    out: list[dict[str, Any]] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValidationError(
                message=f"compound_leg_schedule_v2[{i}] must be an object.",
                details={"index": i},
            )
        lev_raw = row.get("leverage")
        if lev_raw is None:
            raise ValidationError(
                message=f"compound_leg_schedule_v2[{i}] requires integer leverage.",
                details={"index": i},
            )
        try:
            lev = int(lev_raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                message=f"compound_leg_schedule_v2[{i}].leverage must be an integer.",
                details={"index": i},
            ) from exc
        if lev < 1:
            raise ValidationError(
                message=f"compound_leg_schedule_v2[{i}].leverage must be >= 1.",
                details={"index": i, "leverage": lev},
            )
        out.append({"leverage": lev})
    return out


_COMPOUND_V2_CLIENT_ORDER_ID_PREFIX: Final = "pa2l"
_COMPOUND_V2_CLIENT_ORDER_ID_HASH_LEN: Final = 20
_COMPOUND_V2_CLIENT_ORDER_ID_MAX_LEG_INDEX: Final = 98

_COMPOUND_V2_LEG_CLIENT_ORDER_ID_BODY: Final = re.compile(
    rf"^{_COMPOUND_V2_CLIENT_ORDER_ID_PREFIX}-(?P<h>[0-9a-f]{{{_COMPOUND_V2_CLIENT_ORDER_ID_HASH_LEN}}})-(?P<leg>\d{{2}})$",
)


def compound_v2_anchor_short_hash_from_paper_order_id(anchor_paper_order_id: str) -> str:
    """Return the 20-char lowercase hex prefix of a compound-v2 leg ``clientOrderId`` (``pa2l-<hash>-<leg>``)."""
    digest = hashlib.sha256(str(anchor_paper_order_id).encode("utf-8")).hexdigest()
    return digest[:_COMPOUND_V2_CLIENT_ORDER_ID_HASH_LEN]


def try_parse_compound_v2_leg_client_order_id(
    venue_client_order_id: str | None,
) -> tuple[str, int] | None:
    """Parse a compound-v2 leg ``clientOrderId`` (``pa2l-<sha256[:20]>-<leg>``).

    Returns ``(anchor_short_hash_20, leg_index)`` when well-formed; otherwise ``None``.
    Rejects uppercase hex (builder emits lowercase only) and out-of-range leg indexes.
    """
    if not venue_client_order_id:
        return None
    s = str(venue_client_order_id).strip()
    m = _COMPOUND_V2_LEG_CLIENT_ORDER_ID_BODY.fullmatch(s)
    if m is None:
        logger.debug("compound v2 clientOrderId %r is not well-formed", s)
        return None
    h20 = m.group("h")
    leg_index = int(m.group("leg"))
    if leg_index > _COMPOUND_V2_CLIENT_ORDER_ID_MAX_LEG_INDEX:
        logger.debug("compound v2 clientOrderId %r has leg index %d over the cap", s, leg_index)
        return None
    return (h20, leg_index)
