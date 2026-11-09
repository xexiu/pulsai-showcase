"""Unit tests for marketing newsletter audience sync helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.infrastructure.persistence.marketing_newsletter_queries import (
    sync_list_marketing_newsletter_recipients_batch,
)


def test_sync_list_marketing_newsletter_batch_propagates_invalid_limit() -> None:
    session = MagicMock()
    with pytest.raises(ValueError, match="limit"):
        sync_list_marketing_newsletter_recipients_batch(
            session,
            after_email=None,
            limit=0,
        )
    session.execute.assert_not_called()


def test_sync_list_marketing_newsletter_batch_maps_rows() -> None:
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.mappings.return_value.all.return_value = [
        {
            "email": "user@example.com",
            "recipient_kind": "user",
            "user_id": "u1",
            "subscriber_id": None,
            "user_name": "User",
            "locale": "en",
        }
    ]
    session.execute.return_value = execute_result

    out = sync_list_marketing_newsletter_recipients_batch(
        session,
        after_email="a@example.com",
        limit=10,
    )

    assert len(out) == 1
    assert out[0].email == "user@example.com"
    assert out[0].recipient_kind == "user"
    assert out[0].user_id == "u1"
    session.execute.assert_called_once()
