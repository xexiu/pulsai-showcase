"""
Verify paper trading exception hierarchy and details propagation.

TDD RED: written before implementation existed (Slice 2).
"""

from __future__ import annotations


def test_paper_order_error_is_trading_domain_error() -> None:
    from src.shared.exceptions import PaperOrderError, TradingDomainError

    assert issubclass(PaperOrderError, TradingDomainError)


def test_paper_fill_resolution_error_includes_order_id() -> None:
    from src.shared.exceptions import PaperFillResolutionError

    err = PaperFillResolutionError(paper_order_id="abc-123")
    assert err.details["paper_order_id"] == "abc-123"
    assert err.status_code == 500


def test_paper_sltp_placement_error_includes_exchange_and_strategy() -> None:
    from src.shared.exceptions import PaperSLTPPlacementError

    err = PaperSLTPPlacementError(exchange_id="bitget", strategy="exchange_native")
    assert err.details["exchange_id"] == "bitget"
    assert err.details["strategy"] == "exchange_native"
    assert "SL/TP" in err.message


def test_paper_insufficient_margin_error() -> None:
    from src.shared.exceptions import PaperInsufficientMarginError, PaperOrderError

    assert issubclass(PaperInsufficientMarginError, PaperOrderError)
    err = PaperInsufficientMarginError()
    assert err.status_code == 500


def test_paper_compound_direction_error() -> None:
    from src.shared.exceptions import PaperCompoundDirectionError, TradingDomainError

    assert issubclass(PaperCompoundDirectionError, TradingDomainError)
    err = PaperCompoundDirectionError(side="buy", current_price="60000", avg_entry="55000")
    assert err.details["side"] == "buy"
    assert err.details["current_price"] == "60000"
    assert err.details["avg_entry"] == "55000"


def test_paper_exceptions_in_all_exports() -> None:
    from src.shared.exceptions import __all__

    expected = [
        "PaperOrderError",
        "PaperFillResolutionError",
        "PaperSLTPPlacementError",
        "PaperInsufficientMarginError",
        "PaperCompoundDirectionError",
    ]
    for name in expected:
        assert name in __all__, f"{name} missing from __all__"
