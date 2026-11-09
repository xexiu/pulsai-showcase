"""
Telegram Subscription Repository

Handles persistence of Telegram alert subscriptions.

@see src/domain/models/telegram_subscription.py
"""

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.infrastructure.persistence.telegram_subscription_model import TelegramSubscriptionModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TelegramSubscriptionRepository:
    """
    Repository for Telegram subscription persistence.

    PATTERN: Repository (ARCHITECTURE_PATTERNS.md section 2). Not a CRUD passthrough: it owns which chats
    are reachable for which alert (enabled, econ alerts, per symbol), so senders never filter rows themselves.

    USAGE:
    ```python
    repo = TelegramSubscriptionRepository(db_session)
    await repo.set_subscription(chat_id=123456, enabled=True, username="john")
    subscribers = await repo.get_enabled_subscriptions()
    ```
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self._session = session

    async def set_subscription(
        self,
        chat_id: int,
        enabled: bool,
        username: str | None = None,
    ) -> TelegramSubscriptionModel:
        """
        Create or update a subscription.

        Uses upsert (INSERT ... ON CONFLICT UPDATE) for atomic operation.
        If chat_id exists, updates enabled status.
        If chat_id is new, creates subscription.

        Args:
            chat_id: Telegram chat ID
            enabled: Whether alerts are enabled
            username: Optional Telegram username

        Returns:
            The subscription record
        """
        # Upsert using PostgreSQL INSERT ... ON CONFLICT
        stmt = pg_insert(TelegramSubscriptionModel).values(
            chat_id=chat_id,
            alerts_enabled=enabled,
            username=username,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id"],
            set_={
                "alerts_enabled": enabled,
                "username": username or TelegramSubscriptionModel.username,
            },
        )

        await self._session.execute(stmt)
        await self._session.commit()

        # Fetch and return the updated record.
        #
        # `get_by_chat_id` is Optional and this method is not. A blanket suppression sat here and
        # hid that: on a None the caller gets None while the signature promises a model, and the
        # failure surfaces as an AttributeError somewhere downstream with nothing pointing back.
        #
        # The upsert above committed, so the row EXISTS. A None means it was deleted between the
        # commit and this SELECT -- an invariant violation, not an ordinary empty result. Fail
        # loud where the cause is known instead of returning a value the type says is impossible.
        subscription = await self.get_by_chat_id(chat_id)
        if subscription is None:
            msg = f"upsert committed for chat_id={chat_id} but the row was gone on re-read"
            raise RuntimeError(msg)
        return subscription

    async def get_by_chat_id(self, chat_id: int) -> TelegramSubscriptionModel | None:
        """
        Get subscription by Telegram chat ID.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Subscription if found, None otherwise
        """
        stmt = select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == chat_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_enabled_subscriptions(self) -> list[TelegramSubscriptionModel]:
        """
        Get all subscriptions with alerts enabled.

        Returns:
            List of enabled subscriptions
        """
        stmt = (
            select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.alerts_enabled.is_(True)).order_by(TelegramSubscriptionModel.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_chat_ids(self) -> list[int]:
        """
        Get chat IDs of all enabled subscriptions.

        Optimized query that only fetches chat_id column.

        Returns:
            List of chat IDs
        """
        stmt = select(TelegramSubscriptionModel.chat_id).where(TelegramSubscriptionModel.alerts_enabled.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_chat_ids_for_econ_alerts(self) -> list[int]:
        """Chat IDs for users who want economic calendar Telegram alerts."""
        stmt = select(TelegramSubscriptionModel.chat_id).where(
            TelegramSubscriptionModel.alerts_enabled.is_(True),
            TelegramSubscriptionModel.econ_alerts_enabled.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled_chat_ids_for_symbol(self, symbol: str) -> list[int]:
        """
        Get chat IDs for subscribers who want alerts for this symbol.

        Per-symbol filtering logic (Sprint 2.Xd):
        - subscribed_symbols is NULL → ALL symbols (backward compatible)
        - subscribed_symbols is [] → ALL symbols
        - subscribed_symbols contains symbol → this symbol

        Tier policy (product + subscription_entitlements.user_can_receive_telegram_signal_alerts):
        - INNER JOIN users: Telegram must be linked to a PulsAI account (user_id set).
        - Free tier does not receive Telegram signal pushes; Starter+ do; admin/super_admin do even on free tier.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            List of chat IDs that should receive this symbol's alerts
        """
        from sqlalchemy import String, or_
        from sqlalchemy.dialects.postgresql import JSONB

        from src.domain.enums import SubscriptionTier
        from src.infrastructure.persistence.user_model import User, UserRole

        # WHY String cast: JSONB stores Python None as JSON "null" (not SQL NULL)
        # So we check both SQL NULL and JSON null via text comparison
        # Also handle empty array as "all symbols"
        tier_eligible = or_(
            User.role.in_([UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]),
            User.subscription_tier != SubscriptionTier.FREE.value,
        )
        stmt = (
            select(TelegramSubscriptionModel.chat_id)
            .join(User, TelegramSubscriptionModel.user_id == User.id)
            .where(TelegramSubscriptionModel.alerts_enabled.is_(True))
            .where(tier_eligible)
            .where(
                or_(
                    # SQL NULL = all symbols (shouldn't happen with JSONB, but safe)
                    TelegramSubscriptionModel.subscribed_symbols.is_(None),
                    # JSON null = all symbols (JSONB stores Python None as "null")
                    TelegramSubscriptionModel.subscribed_symbols.cast(String) == "null",
                    # Empty array = all symbols
                    TelegramSubscriptionModel.subscribed_symbols.cast(String) == "[]",
                    # Array contains this symbol
                    TelegramSubscriptionModel.subscribed_symbols.cast(JSONB).contains([symbol]),
                )
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def disable_subscription(self, chat_id: int) -> bool:
        """
        Disable alerts for a chat ID.

        Args:
            chat_id: Telegram chat ID

        Returns:
            True if subscription was found and disabled, False otherwise
        """
        stmt = update(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == chat_id).values(alerts_enabled=False)
        result = await self._session.execute(stmt)
        await self._session.commit()
        # justified: SQLAlchemy types `execute` as `Result[Any]`, but a DML statement returns
        # `CursorResult`, which is where `rowcount` lives. Narrowed from a blanket suppression
        # so any OTHER error on this line still fails.
        return result.rowcount > 0  # type: ignore[attr-defined,no-any-return]

    async def count_enabled(self) -> int:
        """
        Count enabled subscriptions.

        Returns:
            Number of enabled subscriptions
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(TelegramSubscriptionModel).where(TelegramSubscriptionModel.alerts_enabled.is_(True))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def link_to_user(self, chat_id: int, user_id: str) -> bool:
        """
        Link a Telegram subscription to a PulsAI user account.

        Args:
            chat_id: Telegram chat ID
            user_id: PulsAI user UUID

        Returns:
            True if linked successfully, False if subscription not found
        """
        stmt = update(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == chat_id).values(user_id=user_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        # justified: SQLAlchemy types `execute` as `Result[Any]`, but a DML statement returns
        # `CursorResult`, which is where `rowcount` lives. Narrowed from a blanket suppression
        # so any OTHER error on this line still fails.
        return result.rowcount > 0  # type: ignore[attr-defined,no-any-return]

    async def update_subscribed_symbols(
        self,
        chat_id: int,
        symbols: list[str] | None,
    ) -> bool:
        """
        Update symbol preferences for a subscription (Sprint 2.Xd).

        Args:
            chat_id: Telegram chat ID
            symbols: List of symbols to receive alerts for.
                     None or [] = ALL symbols.

        Returns:
            True if updated, False if subscription not found
        """
        stmt = update(TelegramSubscriptionModel).where(TelegramSubscriptionModel.chat_id == chat_id).values(subscribed_symbols=symbols)
        result = await self._session.execute(stmt)
        await self._session.commit()
        # justified: SQLAlchemy types `execute` as `Result[Any]`, but a DML statement returns
        # `CursorResult`, which is where `rowcount` lives. Narrowed from a blanket suppression
        # so any OTHER error on this line still fails.
        return result.rowcount > 0  # type: ignore[attr-defined,no-any-return]

    async def get_subscribed_symbols(self, chat_id: int) -> list[str] | None:
        """
        Get symbol preferences for a subscription.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of subscribed symbols, None if all symbols or not found
        """
        stmt = select(TelegramSubscriptionModel.subscribed_symbols).where(TelegramSubscriptionModel.chat_id == chat_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # USER-BASED METHODS (Sprint 2.Xd - FE Symbol Preferences)
    # =========================================================================

    async def get_by_user_id(self, user_id: str) -> TelegramSubscriptionModel | None:
        """
        Get Telegram subscription linked to a user account.

        WHY user_id lookup: FE users are authenticated via JWT (user_id),
        not Telegram chat_id. This enables web UI symbol configuration.

        Args:
            user_id: PulsAI user UUID

        Returns:
            TelegramSubscription if linked, None otherwise
        """
        stmt = select(TelegramSubscriptionModel).where(TelegramSubscriptionModel.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_by_user_id(
        self,
        user_id: str,
        *,
        subscribed_symbols: list[str] | None = None,
        alerts_enabled: bool | None = None,
    ) -> TelegramSubscriptionModel | None:
        """
        Update Telegram subscription settings by user_id.

        WHY separate method: FE users identify via user_id, not chat_id.
        Allows web UI to manage Telegram notification preferences.

        Args:
            user_id: PulsAI user UUID
            subscribed_symbols: Symbol filter (None/[] = all symbols)
            alerts_enabled: Toggle alerts on/off

        Returns:
            Updated subscription if found, None otherwise
        """
        # First get the subscription
        subscription = await self.get_by_user_id(user_id)
        if not subscription:
            return None

        # Update fields if provided
        if subscribed_symbols is not None:
            subscription.subscribed_symbols = subscribed_symbols or None
        if alerts_enabled is not None:
            subscription.alerts_enabled = alerts_enabled

        await self._session.commit()
        await self._session.refresh(subscription)
        return subscription

    async def unlink_user_link(self, user_id: str) -> bool:
        """
        Clear ``user_id`` on the subscription row for this PulsAI account (web self-service unlink).

        The Telegram chat row remains (alerts/username); only the web ↔ Telegram association is removed.

        Args:
            user_id: PulsAI user UUID

        Returns:
            True if a linked row was updated, False if no subscription linked to this user.
        """
        subscription = await self.get_by_user_id(user_id)
        if not subscription:
            return False
        subscription.user_id = None
        await self._session.commit()
        await self._session.refresh(subscription)
        return True

    async def unlink_by_chat_id(self, chat_id: int) -> bool:
        """
        Clear ``user_id`` for this Telegram chat (bot ``/unlink``).

        Returns:
            True if a linked row was updated, False if missing or already unlinked.
        """
        subscription = await self.get_by_chat_id(chat_id)
        if not subscription or subscription.user_id is None:
            return False
        subscription.user_id = None
        await self._session.commit()
        await self._session.refresh(subscription)
        return True
