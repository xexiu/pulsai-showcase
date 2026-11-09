"""HTTP_IDEMPOTENCY_KEY_MAX_LEN SoT regression.

Guards against re-introducing multiple ``= 128`` literal definitions across the
three idempotency-key scopes (paper, demo, HTTP receipts). All three MUST
resolve to the same integer object defined in
``src.shared.constants.http_idempotency``.
"""

from __future__ import annotations

from src.shared.constants import demo_trading, http_idempotency, paper_trading


def test_paper_idempotency_max_len_is_http_max_len() -> None:
    """Paper orders must share the same max length as the HTTP receipt header."""
    assert paper_trading.PAPER_IDEMPOTENCY_KEY_MAX_LEN is http_idempotency.HTTP_IDEMPOTENCY_KEY_MAX_LEN


def test_demo_idempotency_max_len_is_http_max_len() -> None:
    """Demo orders must share the same max length as the HTTP receipt header."""
    assert demo_trading.DEMO_IDEMPOTENCY_KEY_MAX_LEN is http_idempotency.HTTP_IDEMPOTENCY_KEY_MAX_LEN


def test_http_idempotency_max_len_is_128() -> None:
    """Stability pin: 128 is the committed contract for the Idempotency-Key header."""
    assert http_idempotency.HTTP_IDEMPOTENCY_KEY_MAX_LEN == 128


def test_idempotent_replay_headers_only_when_replayed() -> None:
    assert http_idempotency.idempotent_replay_headers(False) is None
    headers = http_idempotency.idempotent_replay_headers(True)
    assert headers == {
        http_idempotency.HTTP_HEADER_IDEMPOTENT_REPLAYED: http_idempotency.HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE,
    }
