"""
Audit Log Domain Model (Sprint 1.8)

SQLAlchemy model for security audit logging.

WHY AUDIT LOGGING?
- Security compliance (track who did what)
- Debugging (trace issues back to actions)
- Analytics (understand user behavior)
- Legal requirements (GDPR, SOC2 readiness)

WHAT WE LOG:
- User authentication events (login, logout, register)
- Admin actions (toggle mock mode, promote model)
- Security events (failed logins, password resets)
- Resource changes (with before/after values)

WHAT WE DON'T LOG:
- Read operations (too noisy, use analytics instead)
- Signal generations (separate signals table)
- Price data (OHLCV table handles this)

@see docs/02-technical/DATABASE_SCHEMA.md for schema
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Required, TypeAlias, TypedDict

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.sqlalchemy_base import Base
from src.shared.utils.datetime_utils import utc_now

# =============================================================================
# Enumerations
# =============================================================================


class EventType(StrEnum):
    """
    Types of events that can be audited.

    WHY STRING ENUM?
    - Human-readable in database
    - Easy to filter and query
    - Compatible with JSON serialization
    """

    # User events (uppercase from initial migration)
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_REGISTER = "USER_REGISTER"
    PASSWORD_RESET = "PASSWORD_RESET"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PROFILE_UPDATE = "PROFILE_UPDATE"
    TOKEN_REFRESH = "token_refresh"
    # Legacy compatibility: old rows may still contain uppercase TOKEN_REFRESH.
    TOKEN_REFRESH_LEGACY = "TOKEN_REFRESH"
    OAUTH_LOGIN = "oauth_login"
    LEGAL_ACCEPTANCE = "legal_acceptance"
    SETTINGS_UPDATE = "settings_update"

    # Subscription events (uppercase from initial migration)
    SUBSCRIPTION_CHANGE = "SUBSCRIPTION_CHANGE"
    SUBSCRIPTION_CANCEL = "SUBSCRIPTION_CANCEL"
    CHECKOUT_STARTED = "checkout_started"

    # Admin events
    ADMIN_ACTION = "ADMIN_ACTION"
    MOCK_MODE_TOGGLE = "MOCK_MODE_TOGGLE"
    MODEL_PROMOTE = "MODEL_PROMOTE"
    MODEL_ROLLBACK = "MODEL_ROLLBACK"
    MODEL_DELETED = "model_deleted"
    MODEL_RESTORED = "model_restored"
    MODEL_PURGED = "model_purged"
    MODEL_HARD_DELETED = "model_hard_deleted"
    MODEL_TAG_CHANGED = "model_tag_changed"
    ENSEMBLE_CONFIG_CHANGED = "ensemble_config_changed"
    META_GATE_ATTACHED = "meta_gate_attached"
    META_GATE_DETACHED = "meta_gate_detached"
    FAILED_MODEL_PROMOTE = "failed_model_promote"
    FAILED_MODEL_ROLLBACK = "failed_model_rollback"
    FAILED_MODEL_DELETED = "failed_model_deleted"
    FAILED_MODEL_RESTORED = "failed_model_restored"
    FAILED_MODEL_PURGED = "failed_model_purged"
    FAILED_MODEL_HARD_DELETED = "failed_model_hard_deleted"
    FAILED_MODEL_TAG_CHANGED = "failed_model_tag_changed"
    FAILED_ENSEMBLE_CONFIG_CHANGED = "failed_ensemble_config_changed"
    FAILED_META_GATE_ACTIVATION = "failed_meta_gate_activation"
    FAILED_AUTO_ROLLBACK = "failed_auto_rollback"
    USER_BAN = "USER_BAN"
    USER_UNBAN = "USER_UNBAN"

    # Trading events (uppercase from initial migration)
    TRADE_EXECUTED = "TRADE_EXECUTED"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    BACKTEST_RUN = "backtest_run"
    BACKTEST_COMPARE = "backtest_compare"
    BACKTEST_DELETED = "backtest_deleted"
    BACKTEST_RENAMED = "backtest_renamed"
    BACKTEST_VISIBILITY_CHANGED = "backtest_visibility_changed"
    COMPARISON_SAVED = "comparison_saved"
    COMPARISON_RENAMED = "comparison_renamed"
    COMPARISON_DELETED = "comparison_deleted"

    # Security events (uppercase from initial migration)
    SECURITY_ALERT = "SECURITY_ALERT"
    FAILED_LOGIN = "FAILED_LOGIN"
    API_KEY_CREATED = "API_KEY_CREATED"
    API_KEY_REVOKED = "API_KEY_REVOKED"

    # Training events (Sprint 2.0c)
    TRAINING_STARTED = "training_started"
    TRAINING_CANCELLED = "training_cancelled"
    TRAINING_COMPLETED = "training_completed"
    TRAINING_FAILED = "training_failed"
    TRAINING_PAUSED = "training_paused"
    TRAINING_RESUMED = "training_resumed"
    TRAINING_VALIDATED = "training_validated"
    TRAINING_JOB_DELETED = "training_job_deleted"
    TRAINING_PANIC_RESET = "training_panic_reset"

    # Marketing / growth automation (newsletter lead → VIP entitlement)
    LEAD_VIP_ENTITLEMENT = "lead_vip_entitlement"
    VIP_CODE_REDEEMED = "vip_code_redeemed"
    NEWSLETTER_SUBSCRIBE = "newsletter_subscribe"
    NEWSLETTER_UNSUBSCRIBE = "newsletter_unsubscribe"

    # System/Anomaly events (Sprint 2.x)
    ANOMALY_DETECTED = "anomaly_detected"
    ANOMALY_RESOLVED = "anomaly_resolved"
    AUTO_ROLLBACK = "auto_rollback"
    RETRAINING_TRIGGERED = "retraining_triggered"
    MODEL_FILES_PURGED = "model_files_purged"
    SIGNAL_OUTCOMES_EVALUATED = "signal_outcomes_evaluated"
    ACCOUNT_INACTIVITY_PURGED = "account_inactivity_purged"

    # User-facing actions
    SIGNAL_GENERATED = "signal_generated"
    # Legacy compatibility: three prod rows (2026-03-27) store the member NAME. Without this
    # member the ORM cannot load them and every /admin/audit page holding one answered 500.
    SIGNAL_GENERATED_LEGACY = "SIGNAL_GENERATED"
    AI_REQUEST = "ai_request"
    CONTACT_INQUIRY = "contact_inquiry"

    # Telegram linking and notifications (Sprint 3.5)
    TELEGRAM_ACCOUNT_LINKED = "telegram_account_linked"
    TELEGRAM_ACCOUNT_UNLINKED = "telegram_account_unlinked"
    TELEGRAM_NOTIFICATION_SENT = "telegram_notification_sent"

    # Email notifications (Sprint 2.4+)
    EMAIL_NOTIFICATION_SENT = "email_notification_sent"
    EMAIL_DIGEST_SENT = "email_digest_sent"

    # Admin/runtime controls
    SCHEDULE_CONFIG_CHANGED = "schedule_config_changed"
    ARENA_REFRESH_TRIGGERED = "arena_refresh_triggered"
    ADMIN_OPTIMIZER_RUN = "admin_optimizer_run"

    # Paper trading (CCXT sandbox) — FROZEN historical values, Epic B deleted the writers.
    # Existing audit_logs rows still reference these names; do not delete the enum members
    # or the read-side queries will break. New auto-order audits use AUTO_ORDER_* below.
    PAPER_ORDER_PLACED = "paper_order_placed"
    PAPER_ORDER_FAILED = "paper_order_failed"
    PAPER_FILL_RESOLVED = "paper_fill_resolved"
    PAPER_FILL_UNKNOWN = "paper_fill_unknown"
    PAPER_BRACKET_TRIGGERED = "paper_bracket_triggered"
    PAPER_COMPOUND_RECALC = "paper_compound_recalc"

    # Epic B (RefactorHuge) — auto-order outcomes for Celery automation runs.
    # Single row per CCXT create_order outcome on the auto path; no DB order row.
    AUTO_ORDER_PLACED_SUCCESS = "auto_order_placed_success"
    AUTO_ORDER_PLACED_FAILED = "auto_order_placed_failed"
    EXCHANGE_CONNECTED = "exchange_connected"
    EXCHANGE_DISCONNECTED = "exchange_disconnected"
    EXCHANGE_VERIFY_FAILED = "exchange_verify_failed"
    EXCHANGE_VERIFY_SUCCEEDED = "exchange_verify_succeeded"
    FUTURES_AUTH_DENIED = "futures_auth_denied"
    TRADING_VALIDATION_FAILED = "trading_validation_failed"
    TRADING_ENDPOINT_RATE_LIMITED = "trading_endpoint_rate_limited"
    TRADING_MODE_SELECTED = "trading_mode_selected"
    EXCHANGE_ENDPOINT_RATE_LIMITED = "exchange_endpoint_rate_limited"
    FUTURES_LEVERAGE_TIERS_VIEWED = "futures_leverage_tiers_viewed"

    # Trading automation (Manual vs Auto) — policy / lifecycle audit
    TRADING_AUTOMATION_MUTATED = "trading_automation_mutated"
    FULL_AUTO_TRADING_CONSENT_ACCEPTED = "full_auto_trading_consent_accepted"

    # Epic C — server-stored exchange keys (vault → server upload lifecycle).
    # ``UPLOADED``/``REVOKED`` are explicit user actions; ``USED`` records auto-mode
    # consumption; ``EXPIRED`` is automatic via the daily expiry task.
    EXCHANGE_SERVER_KEY_UPLOADED = "exchange_server_key_uploaded"
    EXCHANGE_SERVER_KEY_REVOKED = "exchange_server_key_revoked"
    EXCHANGE_SERVER_KEY_USED = "exchange_server_key_used"
    EXCHANGE_SERVER_KEY_EXPIRED = "exchange_server_key_expired"


#: The one home for legacy spellings: a member that exists only so old rows load, mapped to the
#: member new rows are written with. The repository's filter aliases and the API's serialized value
#: are both derived from it, so a third legacy label is one line here, not three edits.
LEGACY_EVENT_TYPES: dict[EventType, EventType] = {
    EventType.TOKEN_REFRESH_LEGACY: EventType.TOKEN_REFRESH,
    EventType.SIGNAL_GENERATED_LEGACY: EventType.SIGNAL_GENERATED,
}


def canonical_event_type(event_type: EventType) -> EventType:
    """Return the member new rows are written with; a legacy spelling maps to it."""
    return LEGACY_EVENT_TYPES.get(event_type, event_type)


class AuditAction(StrEnum):
    """
    CRUD actions for audit entries.

    WHY SEPARATE FROM EVENT_TYPE?
    - Event type = WHAT happened (login, model promote)
    - Action = HOW it changed the system (create, update, delete)
    - Allows filtering: "show all DELETE actions" regardless of event type
    """

    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditResourceType(StrEnum):
    """Resource categories referenced by audit entries."""

    USER = "user"
    MODEL = "model"
    MODEL_CANDIDATE = "model_candidate"
    MODEL_REGISTRY = "model_registry"
    MODEL_FILES = "model_files"
    SIGNAL = "signal"
    SIGNAL_OUTCOMES = "signal_outcomes"
    AI = "ai"
    BACKTEST = "backtest"
    COMPARISON = "comparison"
    INFERENCE_COMPARE = "inference_compare"
    SIGNAL_DB_REPLAY_AUDIT = "signal_db_replay_audit"
    SUBSCRIPTION = "subscription"
    SUBSCRIPTION_TIER = "subscription_tier"
    NEWSLETTER_SUBSCRIBER = "newsletter_subscriber"
    VIP_LAUNCH_CODE = "vip_launch_code"
    CONTACT_INQUIRY = "contact_inquiry"
    LEGAL_POLICY = "legal_policy"
    ANOMALY = "anomaly"
    TRAINING_JOB = "training_job"
    TRAINING_CONFIG = "training_config"
    TRAINING_TRIGGER = "training_trigger"
    TRAINING_PANIC_RESET = "training_panic_reset"
    SCHEDULE_CONFIG = "schedule_config"
    ARENA = "arena"
    ADMIN_OPTIMIZER = "admin_optimizer"
    TELEGRAM_SUBSCRIPTION = "telegram_subscription"
    PAPER_TRADING = "paper_trading"
    EXCHANGE_CONNECTION = "exchange_connection"
    TRADING_AUTOMATION = "trading_automation"


class RiskLevel(StrEnum):
    """
    Risk classification for audit events.

    WHY RISK LEVELS?
    - Prioritize security monitoring
    - Filter dashboard by severity
    - Trigger alerts for critical events

    RISK ASSIGNMENT GUIDELINES:
    - LOW: Normal user actions (login, profile update)
    - MEDIUM: Administrative actions (mock mode toggle)
    - HIGH: Sensitive actions (model promote, user ban)
    - CRITICAL: Security incidents (failed logins, alerts)
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuditLogFields(TypedDict, total=False):
    """The caller-supplied values of one audit row -- written ONCE, so the repository port and
    its implementation take ``**fields: Unpack[AuditLogFields]`` instead of each restating the
    ten keywords (the copy the duplicate-lines ratchet measured). Omitted keys take the column
    defaults (``risk_level`` LOW, the rest NULL).
    """

    event_type: Required[EventType | str]
    action: Required[AuditAction]
    status: Required[str]
    user_id: str | None
    resource_type: str | None
    resource_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    risk_level: RiskLevel


AuditSortBy: TypeAlias = Literal["time", "user_id", "event_type", "status", "risk_level", "ip_address"]
SortDir: TypeAlias = Literal["asc", "desc"]


class AuditLogQuery(TypedDict, total=False):
    """The keyword arguments the audit listing accepts, named once for the port and the repository.

    Lives beside the entity, not in the repository: the domain port may import this model module
    (an import-linter allow-listed edge) and nothing else from infrastructure.
    """

    page: int
    per_page: int
    user_id: str | None
    event_type: EventType | str | None
    event_types: list[EventType | str] | None
    risk_level: RiskLevel | str | None
    since: datetime | None
    until: datetime | None
    sort_by: AuditSortBy
    sort_dir: SortDir


# =============================================================================
# Model
# =============================================================================


class AuditLog(Base):
    """
    Audit log entry for security and compliance tracking.

    ARCHITECT NOTES:
    - Uses BIGSERIAL for id (more entries than UUID space needed)
    - Stores IP as string (simpler than INET type for SQLAlchemy)
    - Details as JSON for flexibility (different events have different data)
    - No foreign key constraint on user_id (user might be deleted)
    """

    __tablename__ = "audit_logs"

    # Primary key - BIGSERIAL for high-volume logging
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Timestamp - when the event occurred
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
        index=True,  # Frequently queried by time range
    )

    # Actor - who performed the action (nullable for system events)
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,  # Frequently queried by user
    )

    # Context - where the action came from
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Event classification
    event_type: Mapped[EventType] = mapped_column(
        SqlEnum(EventType, name="event_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,  # Frequently filtered by event type
    )
    action: Mapped[AuditAction] = mapped_column(
        SqlEnum(AuditAction, name="audit_action", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # success, failure, pending

    # Resource reference - what was affected
    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # user, model, signal, etc.
    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )  # UUID or other identifier

    # Additional context
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Risk assessment.
    # No index=True: the auto-named ``ix_audit_logs_risk_level`` was dropped in
    # ``20260610_db_hygiene_dead_indexes_ohlcv_chunk_interval`` — risk_level is
    # low-selectivity (prod ~99% LOW) so the planner never used it. Keep
    # create_all aligned with the migrated DB.
    risk_level: Mapped[RiskLevel] = mapped_column(
        SqlEnum(RiskLevel, name="risk_level", values_callable=lambda x: [e.value for e in x]),
        default=RiskLevel.LOW,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.id}: {self.event_type.value} ({self.status})>"
