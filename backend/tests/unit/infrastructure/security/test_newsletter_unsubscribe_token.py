"""Signed newsletter unsubscribe tokens (itsdangerous)."""

from src.infrastructure.security.newsletter_unsubscribe_token import (
    create_newsletter_unsubscribe_token,
    parse_newsletter_unsubscribe_token,
)
from src.infrastructure.security.user_marketing_unsubscribe_token import (
    create_user_marketing_unsubscribe_token,
    parse_user_marketing_unsubscribe_token,
)


def test_unsubscribe_token_round_trip() -> None:
    sid = "550e8400-e29b-41d4-a716-446655440000"
    token = create_newsletter_unsubscribe_token(sid)
    assert parse_newsletter_unsubscribe_token(token) == sid


def test_unsubscribe_token_rejects_garbage() -> None:
    assert parse_newsletter_unsubscribe_token("not-a-valid-token") is None


def test_user_marketing_unsubscribe_token_round_trip() -> None:
    user_id = "550e8400-e29b-41d4-a716-446655440001"
    token = create_user_marketing_unsubscribe_token(user_id)
    assert parse_user_marketing_unsubscribe_token(token) == user_id


def test_user_marketing_unsubscribe_token_rejects_garbage() -> None:
    assert parse_user_marketing_unsubscribe_token("not-a-valid-token") is None
