"""
Tests for TelegramSubscriptionModel Model

Tests the persistence of Telegram alert subscriptions.

Uses sync SQLAlchemy pattern (same as test_signal_repository.py).
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.infrastructure.persistence.telegram_subscription_model import TelegramSubscriptionModel
from src.infrastructure.persistence.user_model import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestTelegramSubscriptionModel:
    """Tests for TelegramSubscriptionModel model persistence."""

    def test_subscription_creation(self, model_db_session: Session) -> None:
        """
        Test that TelegramSubscriptionModel model can be created and persisted.

        BEHAVIOR: Subscription should be saved with all fields populated.
        """
        # Arrange
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=123456789,
            username="testuser",
            alerts_enabled=True,
        )

        # Act
        model_db_session.add(subscription)
        model_db_session.commit()

        # Assert
        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 123456789))
        saved = result.scalar_one()

        assert saved.chat_id == 123456789
        assert saved.username == "testuser"
        assert saved.alerts_enabled is True

    def test_subscription_defaults(self, model_db_session: Session) -> None:
        """
        Test that default values are set correctly.

        BEHAVIOR: alerts_enabled should default to True, user_id to None.
        """
        # Arrange
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=987654321,
        )

        # Act
        model_db_session.add(subscription)
        model_db_session.commit()

        # Assert
        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 987654321))
        saved = result.scalar_one()

        assert saved.alerts_enabled is True  # Default
        assert saved.user_id is None  # Default
        assert saved.username is None  # Default

    def test_unique_chat_id_constraint(self, model_db_session: Session) -> None:
        """
        Test that chat_id is unique.

        BEHAVIOR: Duplicate chat_id should raise an error.
        """
        from sqlalchemy.exc import IntegrityError

        # Arrange
        sub1 = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=111222333,
        )
        model_db_session.add(sub1)
        model_db_session.commit()

        # Act & Assert
        sub2 = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=111222333,  # Same chat_id
        )
        model_db_session.add(sub2)

        with pytest.raises(IntegrityError):
            model_db_session.commit()

    def test_query_enabled_subscriptions(self, model_db_session: Session) -> None:
        """
        Test filtering subscriptions by enabled status.

        BEHAVIOR: Should return only enabled subscriptions.
        """
        # Arrange
        subs = [
            TelegramSubscriptionModel(id=str(uuid4()), chat_id=100, alerts_enabled=True),
            TelegramSubscriptionModel(id=str(uuid4()), chat_id=200, alerts_enabled=False),
            TelegramSubscriptionModel(id=str(uuid4()), chat_id=300, alerts_enabled=True),
        ]
        for s in subs:
            model_db_session.add(s)
        model_db_session.commit()

        # Act
        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.alerts_enabled.is_(True)))
        enabled = list(result.scalars().all())

        # Assert
        chat_ids = [s.chat_id for s in enabled]
        assert 100 in chat_ids
        assert 300 in chat_ids
        assert 200 not in chat_ids

    def test_link_subscription_to_user(self, model_db_session: Session) -> None:
        """
        Test linking subscription to a PulsAI user.

        BEHAVIOR: user_id should be set and queryable.
        """
        # Arrange - create user
        user = User(
            id=str(uuid4()),
            email="telegram_link_test@example.com",
            password_hash="hashed",
            name="Test User",
        )
        model_db_session.add(user)
        model_db_session.commit()

        # Arrange - create subscription
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=444555666,
            user_id=user.id,
        )
        model_db_session.add(subscription)
        model_db_session.commit()

        # Assert
        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 444555666))
        saved = result.scalar_one()

        assert saved.user_id == user.id

    def test_subscription_repr(self) -> None:
        """Test string representation of subscription."""
        sub_enabled = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=123,
            alerts_enabled=True,
        )
        sub_disabled = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=456,
            alerts_enabled=False,
        )

        assert "enabled" in repr(sub_enabled)
        assert "disabled" in repr(sub_disabled)


# =============================================================================
# TDD: Per-Symbol Filtering Tests (Sprint 2.Xd Enhancement)
# =============================================================================


class TestSubscribedSymbolsModel:
    """
    TDD tests for per-symbol subscription filtering.

    FEATURE: Users can choose which trading pairs to receive alerts for.
    - subscribed_symbols = NULL or [] → ALL symbols (backward compatible)
    - subscribed_symbols = ["BTC/USDT"] → Only BTC/USDT alerts
    """

    def test_subscribed_symbols_default_is_null(self, model_db_session: Session) -> None:
        """
        BEHAVIOR: subscribed_symbols should default to NULL (all symbols).

        WHY NULL default: Backward compatible - existing users get all alerts.
        """
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=777888999,
        )
        model_db_session.add(subscription)
        model_db_session.commit()

        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 777888999))
        saved = result.scalar_one()

        assert saved.subscribed_symbols is None

    def test_subscribed_symbols_stores_array(self, model_db_session: Session) -> None:
        """
        BEHAVIOR: subscribed_symbols should store an array of symbol strings.

        WHY array: Simple, flexible, JSON-compatible.
        """
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=111999222,
            subscribed_symbols=["BTC/USDT", "ETH/USDT"],
        )
        model_db_session.add(subscription)
        model_db_session.commit()

        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 111999222))
        saved = result.scalar_one()

        assert saved.subscribed_symbols == ["BTC/USDT", "ETH/USDT"]
        assert "BTC/USDT" in saved.subscribed_symbols  # type: ignore[operator]
        assert "SOL/USDT" not in saved.subscribed_symbols  # type: ignore[operator, union-attr]

    def test_subscribed_symbols_can_be_empty_array(self, model_db_session: Session) -> None:
        """
        BEHAVIOR: Empty array should be allowed (means all symbols).

        WHY: Empty array and NULL both mean "all symbols" for simplicity.
        """
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=333444555,
            subscribed_symbols=[],
        )
        model_db_session.add(subscription)
        model_db_session.commit()

        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 333444555))
        saved = result.scalar_one()

        assert saved.subscribed_symbols == []

    def test_query_subscriptions_by_symbol(self, model_db_session: Session) -> None:
        """
        BEHAVIOR: Should be able to filter subscriptions that include a symbol.

        WHY: NotificationService needs to find who wants BTC/USDT alerts.
        """
        # Create subscriptions with different symbol preferences
        subs = [
            TelegramSubscriptionModel(
                id=str(uuid4()),
                chat_id=1001,
                alerts_enabled=True,
                subscribed_symbols=None,  # All symbols
            ),
            TelegramSubscriptionModel(
                id=str(uuid4()),
                chat_id=1002,
                alerts_enabled=True,
                subscribed_symbols=["BTC/USDT"],  # Only BTC
            ),
            TelegramSubscriptionModel(
                id=str(uuid4()),
                chat_id=1003,
                alerts_enabled=True,
                subscribed_symbols=["ETH/USDT"],  # Only ETH
            ),
            TelegramSubscriptionModel(
                id=str(uuid4()),
                chat_id=1004,
                alerts_enabled=True,
                subscribed_symbols=["BTC/USDT", "ETH/USDT"],  # Both
            ),
            TelegramSubscriptionModel(
                id=str(uuid4()),
                chat_id=1005,
                alerts_enabled=False,  # Disabled
                subscribed_symbols=["BTC/USDT"],
            ),
        ]
        for s in subs:
            model_db_session.add(s)
        model_db_session.commit()

        # Query: Who should receive BTC/USDT alerts?
        # Answer: 1001 (all), 1002 (BTC), 1004 (both) - NOT 1003 (ETH only), NOT 1005 (disabled)
        from sqlalchemy import String, or_
        from sqlalchemy.dialects.postgresql import JSONB

        symbol = "BTC/USDT"
        # WHY String cast: JSONB stores Python None as JSON "null" (not SQL NULL)
        # This approach matches the repository implementation
        stmt = (
            select(TelegramSubscriptionModel.chat_id)
            .where(TelegramSubscriptionModel.alerts_enabled.is_(True))
            .where(
                or_(
                    # SQL NULL (rare with JSONB)
                    TelegramSubscriptionModel.subscribed_symbols.is_(None),
                    # JSON null (JSONB stores Python None as "null")
                    TelegramSubscriptionModel.subscribed_symbols.cast(String) == "null",
                    # Empty array
                    TelegramSubscriptionModel.subscribed_symbols.cast(String) == "[]",
                    # Contains symbol
                    TelegramSubscriptionModel.subscribed_symbols.cast(JSONB).contains([symbol]),
                )
            )
        )
        result = model_db_session.execute(stmt)
        chat_ids = list(result.scalars().all())

        assert 1001 in chat_ids  # All symbols
        assert 1002 in chat_ids  # Subscribed to BTC
        assert 1004 in chat_ids  # Subscribed to BTC and ETH
        assert 1003 not in chat_ids  # Only ETH
        assert 1005 not in chat_ids  # Disabled


class TestLinkToUser:
    """
    Tests for linking Telegram subscription to PulsAI user account.

    Sprint 2.Xd: /link command enables FE symbol preferences.

    BEHAVIOR tests:
    - User can link their Telegram to their PulsAI account
    - Linking enables FE to show and configure symbol preferences
    """

    def test_link_subscription_to_user_by_chat_id(self, model_db_session: Session) -> None:
        """
        BEHAVIOR: Can link subscription to user using chat_id.
        WHY: /link command uses chat_id to find subscription.
        """
        from uuid import uuid4

        from src.infrastructure.persistence.telegram_subscription_model import TelegramSubscriptionModel
        from src.infrastructure.persistence.user_model import User

        # Create user
        user = User(
            id=str(uuid4()),
            email="linktest@example.com",
            password_hash="hash",
        )
        model_db_session.add(user)

        # Create subscription (not linked)
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=555666777,
        )
        model_db_session.add(subscription)
        model_db_session.commit()

        # Link via update
        from sqlalchemy import update

        model_db_session.execute(update(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 555666777).values(user_id=user.id))
        model_db_session.commit()

        # Verify link
        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 555666777))
        linked = result.scalar_one()
        assert linked.user_id == user.id

    def test_get_subscription_by_user_id(self, model_db_session: Session) -> None:
        """
        BEHAVIOR: Can retrieve subscription by user_id.
        WHY: FE uses user_id (from JWT) to get subscription.
        """
        from uuid import uuid4

        from src.infrastructure.persistence.telegram_subscription_model import TelegramSubscriptionModel
        from src.infrastructure.persistence.user_model import User

        # Create user FIRST
        user = User(
            id=str(uuid4()),
            email="getbyuser@example.com",
            password_hash="hash",
        )
        model_db_session.add(user)
        model_db_session.commit()  # Commit user before referencing

        # Now create subscription with user_id FK
        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=888999000,
            user_id=user.id,
            subscribed_symbols=["BTC/USDT"],
        )
        model_db_session.add(subscription)
        model_db_session.commit()

        # Query by user_id
        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.user_id == user.id))
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.chat_id == 888999000
        assert found.subscribed_symbols == ["BTC/USDT"]

    def test_unlinked_subscription_has_null_user_id(self, model_db_session: Session) -> None:
        """
        BEHAVIOR: Subscription without link has null user_id.
        WHY: FE shows "not linked" message when user_id is null.
        """
        from uuid import uuid4

        from src.infrastructure.persistence.telegram_subscription_model import TelegramSubscriptionModel

        subscription = TelegramSubscriptionModel(
            id=str(uuid4()),
            chat_id=111222333,
        )
        model_db_session.add(subscription)
        model_db_session.commit()

        result = model_db_session.execute(select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == 111222333))
        found = result.scalar_one()
        assert found.user_id is None


class TestTheUpsertPostcondition:
    """`set_subscription` promised a model and could return None; a blanket suppression hid it.

    It is declared `-> TelegramSubscriptionModel`, and its last statement re-reads the row through
    `get_by_chat_id`, which is `-> TelegramSubscriptionModel | None`. A blanket type suppression
    sat on that line, so the mismatch never surfaced. Lifting it, mypy named it exactly:

        Incompatible return value type (got "TelegramSubscriptionModel | None",
                                       expected "TelegramSubscriptionModel")  [return-value]

    Not theoretical: on a None the caller gets None where the type promises a model, and the
    failure appears later as an AttributeError with nothing pointing back to this method.

    The upsert COMMITS before the re-read, so the row exists by construction. A None means it was
    deleted in between — an invariant violation, not an ordinary empty result — so the honest
    response is to fail where the cause is known.
    """

    @staticmethod
    def _repo_with_reread(result):
        from unittest.mock import AsyncMock

        from src.infrastructure.persistence.telegram_subscription_repository import (
            TelegramSubscriptionRepository,
        )

        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        repo = TelegramSubscriptionRepository(session=session)
        repo.get_by_chat_id = AsyncMock(return_value=result)
        return repo

    @pytest.mark.asyncio
    async def test_a_vanished_row_raises_instead_of_returning_none(self) -> None:
        repo = self._repo_with_reread(None)

        with pytest.raises(RuntimeError, match="row was gone on re-read"):
            await repo.set_subscription(chat_id=4242, enabled=True)

    @pytest.mark.asyncio
    async def test_the_error_names_the_chat_id(self) -> None:
        """A failure with no identifier costs an archaeology session to place."""
        repo = self._repo_with_reread(None)

        with pytest.raises(RuntimeError, match="4242"):
            await repo.set_subscription(chat_id=4242, enabled=True)

    @pytest.mark.asyncio
    async def test_the_ordinary_path_returns_the_row_unchanged(self) -> None:
        """The guard must not disturb the case that always worked."""
        sentinel = object()
        repo = self._repo_with_reread(sentinel)

        assert await repo.set_subscription(chat_id=4242, enabled=True) is sentinel

    @pytest.mark.asyncio
    async def test_it_commits_before_re_reading(self) -> None:
        """The postcondition holds only because the write is committed first."""
        repo = self._repo_with_reread(object())

        await repo.set_subscription(chat_id=1, enabled=False)

        repo._session.commit.assert_awaited()
