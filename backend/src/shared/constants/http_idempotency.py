"""
HTTP ``Idempotency-Key`` header — cross-route constants (trading orders, automation mutations).

Canonical SoT for the ``128``-char idempotency key max length used by the paper
order, demo order, and HTTP receipt tables. Paper/demo specific constants
re-export from here so clients can reuse key length assumptions.
"""

from __future__ import annotations

from typing import Final

HTTP_IDEMPOTENCY_KEY_MAX_LEN: Final[int] = 128

# Response header emitted on idempotent replays.
#
# Stripe-style convention: when a request with an ``Idempotency-Key`` resolves
# to a previously-persisted result rather than executing a fresh operation,
# the response carries ``X-Idempotent-Replayed: true`` so clients (and ops
# dashboards) can distinguish a real action from a cache hit. The header is
# only set when ``true`` — its absence implies a fresh execution.
HTTP_HEADER_IDEMPOTENT_REPLAYED: Final[str] = "X-Idempotent-Replayed"
HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE: Final[str] = "true"


def idempotent_replay_headers(replayed_http: bool) -> dict[str, str] | None:
    """Return replay headers for JSONResponse, or None when not a replay."""
    if not replayed_http:
        return None
    return {HTTP_HEADER_IDEMPOTENT_REPLAYED: HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE}


# Receipt ``operation`` discriminator (stored on ``api_http_idempotency_receipts``).
HTTP_IDEM_OP_AUTOMATION_CREATE: Final[str] = "automation_create"
HTTP_IDEM_OP_AUTOMATION_PROMOTE: Final[str] = "automation_promote"
HTTP_IDEM_OP_AUTOMATION_PROMOTE_PUBLIC: Final[str] = "automation_promote_public"
HTTP_IDEM_OP_AUTOMATION_CATALOG: Final[str] = "automation_catalog"
HTTP_IDEM_OP_AUTOMATION_PATCH: Final[str] = "automation_patch"
HTTP_IDEM_OP_AUTOMATION_SELECT_AS_ACTIVE: Final[str] = "automation_select_as_active"
HTTP_IDEM_OP_BILLING_CHECKOUT_SESSION: Final[str] = "billing_checkout_session"
HTTP_IDEM_OP_BILLING_PORTAL_SESSION: Final[str] = "billing_portal_session"
HTTP_IDEM_OP_ADMIN_BILLING_REFUND: Final[str] = "admin_billing_refund"
HTTP_IDEM_OP_ADMIN_BILLING_SYNC_TIER: Final[str] = "admin_billing_sync_tier"
HTTP_IDEM_OP_ADMIN_SEND_PASSWORD_RESET: Final[str] = "admin_send_password_reset"
HTTP_IDEM_OP_ADMIN_RESET_LEGAL_ACCEPTANCE: Final[str] = "admin_reset_legal_acceptance"
HTTP_IDEM_OP_ADMIN_ISSUE_INVITE_CODE: Final[str] = "admin_issue_invite_code"
HTTP_IDEM_OP_ADMIN_SEND_INVITE_EMAIL: Final[str] = "admin_send_invite_email"
HTTP_IDEM_OP_ADMIN_ANONYMIZE_USER: Final[str] = "admin_anonymize_user"
HTTP_IDEM_OP_ADMIN_PATCH_USER: Final[str] = "admin_patch_user"
HTTP_IDEM_OP_ADMIN_REQUIRE_LEGAL_REACCEPT: Final[str] = "admin_require_legal_reaccept"
HTTP_IDEM_OP_ADMIN_BLOCK_IP: Final[str] = "admin_block_ip"
HTTP_IDEM_OP_ADMIN_UNBLOCK_IP: Final[str] = "admin_unblock_ip"
HTTP_IDEM_OP_ADMIN_SYSTEM_CONTROLS_PATCH: Final[str] = "admin_system_controls_patch"
HTTP_IDEM_OP_ADMIN_SYSTEM_CONTROLS_DELETE_OVERRIDE: Final[str] = "admin_system_controls_delete_override"
HTTP_IDEM_OP_ADMIN_ANNOUNCEMENT_SEND: Final[str] = "admin_announcement_send"
HTTP_IDEM_OP_EXCHANGE_CONNECT: Final[str] = "exchange_connect"
HTTP_IDEM_OP_EXCHANGE_VERIFY: Final[str] = "exchange_verify"
HTTP_IDEM_OP_EXCHANGE_DISCONNECT: Final[str] = "exchange_disconnect"
HTTP_IDEM_OP_EXCHANGE_UPLOAD_SERVER_KEYS: Final[str] = "exchange_upload_server_keys"
HTTP_IDEM_OP_EXCHANGE_REVOKE_SERVER_KEYS: Final[str] = "exchange_revoke_server_keys"
