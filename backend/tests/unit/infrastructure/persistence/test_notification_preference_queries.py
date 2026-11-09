"""Tests for notification preference SQL helpers (sync + select builders)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.infrastructure.persistence.notification_preference_queries import (
    sync_list_users_eligible_for_weekly_digest_email_batch,
)


def test_sync_list_weekly_digest_batch_propagates_invalid_limit() -> None:
    session = MagicMock()
    with pytest.raises(ValueError, match="limit"):
        sync_list_users_eligible_for_weekly_digest_email_batch(
            session,
            after_user_id=None,
            limit=0,
        )
    session.execute.assert_not_called()


def test_sync_list_weekly_digest_batch_returns_scalars_from_session() -> None:
    user = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [user]
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    session = MagicMock()
    session.execute.return_value = execute_result

    out = sync_list_users_eligible_for_weekly_digest_email_batch(
        session,
        after_user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        limit=10,
    )

    assert out == [user]
    session.execute.assert_called_once()
    (stmt_arg,) = session.execute.call_args[0]
    assert str(stmt_arg).startswith("SELECT")
