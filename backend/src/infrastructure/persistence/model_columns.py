"""The column shapes several ORM models share: a string-UUID primary key and the owning user's id.

IMPORTERS/CALLERS: password_reset_token_model.PasswordResetTokenModel, trading_automation_model.TradingAutomationModel;
tests/unit/infrastructure/persistence/test_model_columns.py. AFFECTED API: uuid_primary_key, owning_user_id (new).
DATA SCHEMAS: none -- each model's compiled DDL is byte-identical to the copies these replace (checked 2026-10-18).

WHY (ORM-RESET-BACKREF, 2026-10-18): the copy-paste gate refused a change to the reset-token model because its id /
user_id block was the same 12 lines as the trading-automation model's -- 6 models repeat the owner key and 21 the UUID
key. A function per shape, called once per model, so every table gets its own Column (SQLAlchemy never lets two tables
share one). The other copies move here as their files are touched (8c CLONES-ALL).

REUSE-AUDIT: sqlalchemy_base.Base (the declarative base; one job, kept); no column helper or mixin existed under
infrastructure/persistence (searched Mixin, uuid_primary_key, user_id_column, user_fk: 0).
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import MappedColumn, mapped_column

#: The table and column every owner key points at; a user's rows go with the user (the database cascades).
USERS_ID: str = "users.id"


def _new_uuid() -> str:
    return str(uuid4())


def uuid_primary_key() -> MappedColumn[str]:
    """A primary key stored as a UUID, read as its string, minted fresh on every insert."""
    return mapped_column(UUID(as_uuid=False), primary_key=True, default=_new_uuid)


def owning_user_id() -> MappedColumn[str]:
    """The owning user's id: required, indexed, and removed with the user (ON DELETE CASCADE in the database)."""
    return mapped_column(UUID(as_uuid=False), ForeignKey(USERS_ID, ondelete="CASCADE"), nullable=False, index=True)
