"""
Domain Model Tests

Tests for SQLAlchemy models (User, Signal, OHLCVModel).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.domain.enums import RegistrationSource
from src.infrastructure.persistence.signal_model import Signal
from src.infrastructure.persistence.user_model import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def test_user_registration_source_round_trip(model_db_session: Session) -> None:
    """
    User.registration_source round-trips when stored as enum value ('direct') in DB.

    REGRESSION: SqlEnum must use values_callable so DB value 'direct' loads without LookupError.
    """
    user = User(
        id=str(uuid4()),
        email="reg_src@example.com",
        password_hash="hashed",
        role="user",
        subscription_tier="free",
        registration_source=RegistrationSource.DIRECT.value,
    )
    model_db_session.add(user)
    model_db_session.commit()
    model_db_session.refresh(user)

    assert user.registration_source == RegistrationSource.DIRECT.value


def test_create_user(model_db_session: Session) -> None:
    """Test creating a user in the database."""
    user = User(
        id=str(uuid4()),
        email="test@example.com",
        password_hash="hashed_password_here",
        name="Test User",
        role="user",
        subscription_tier="free",
        locale="es",
    )

    model_db_session.add(user)
    model_db_session.commit()
    model_db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.role == "user"
    assert user.subscription_tier == "free"
    assert user.locale == "es"
    assert user.is_active is True
    assert user.is_verified is False


def test_user_default_values(model_db_session: Session) -> None:
    """Test that user has correct default values."""
    user = User(
        id=str(uuid4()),
        email="defaults@example.com",
        password_hash="hashed",
    )

    model_db_session.add(user)
    model_db_session.commit()
    model_db_session.refresh(user)

    assert user.role == "user"
    assert user.subscription_tier == "free"
    assert user.is_active is True
    assert user.is_verified is False
    assert user.locale == "es"  # Default locale is Spanish
    assert user.created_at is not None
    assert user.updated_at is not None


def test_create_signal(model_db_session: Session, sample_signal_data: dict[str, Any]) -> None:
    """Test creating a signal in the database."""
    signal = Signal(
        id=str(uuid4()),
        symbol=sample_signal_data["symbol"],
        timeframe=sample_signal_data["timeframe"],
        action=sample_signal_data["action"],
        confidence=sample_signal_data["confidence"],
        price=sample_signal_data["price"],
        model_version=sample_signal_data["model_version"],
        indicators=sample_signal_data["indicators"],
    )

    model_db_session.add(signal)
    model_db_session.commit()
    model_db_session.refresh(signal)

    assert signal.id is not None
    assert signal.symbol == "BTC/USDT"
    assert signal.action == "BUY"
    assert signal.confidence == 85.5
    assert signal.price == 45000.00
    assert signal.indicators["rsi"] == 45.2


def test_signal_created_at_auto(model_db_session: Session) -> None:
    """Test that signal created_at is set automatically."""
    signal = Signal(
        id=str(uuid4()),
        symbol="ETH/USDT",
        timeframe="4h",
        action="SELL",
        confidence=72.0,
        price=3000.00,
        model_version="v1.0.0",
        indicators={},
    )

    before_create = datetime.now(UTC)
    model_db_session.add(signal)
    model_db_session.commit()
    model_db_session.refresh(signal)

    assert signal.created_at is not None
    # Allow some tolerance for timing
    assert signal.created_at >= before_create.replace(microsecond=0)


def test_user_repr() -> None:
    """Test User model string representation."""
    user = User(
        id=str(uuid4()),
        email="repr@example.com",
        password_hash="hashed",
    )

    assert "repr@example.com" in repr(user)


def test_signal_repr() -> None:
    """Test Signal model string representation."""
    signal = Signal(
        id=str(uuid4()),
        symbol="BTC/USDT",
        timeframe="1h",
        action="BUY",
        confidence=85.0,
        price=45000.00,
        model_version="v1.0.0",
        indicators={},
    )

    repr_str = repr(signal)
    assert "BTC/USDT" in repr_str
    assert "BUY" in repr_str
    assert "85" in repr_str
