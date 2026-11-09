"""Behaviour: the automation gate that decides PAPER vs real-money MAINNET execution.

This module had NO tests. It is read by the Celery automation executor to decide whether a tick
places orders on mainnet with real funds, and both of its gates were unpinned — a flag flip or a
role-set edit could have inverted it with nothing failing.

The policy is two independent gates, both required:

1. the connection row opted in (``mainnet_execution_enabled``), and
2. the account passes the feature gate — ``feature_live_trading`` globally, or
   ``feature_live_trading_internal_preview`` for staff on staging.

The full truth table is pinned below rather than the happy path, because for this function the
dangerous direction is a FALSE POSITIVE: every unpinned combination is one that could return
LIVE when it should have returned PAPER.
"""

from __future__ import annotations

import pytest

from src.domain.services.trading_live_execution_mode import (
    resolve_automation_ccxt_execution_mode,
    user_may_use_live_trading,
)
from src.shared.constants.paper_trading import TRADING_MODE_LIVE, TRADING_MODE_PAPER


class TestOptInIsRequiredRegardlessOfFlags:
    """Gate 1 alone can force PAPER — no flag combination may override the connection row."""

    @pytest.mark.parametrize("live_enabled", [True, False])
    @pytest.mark.parametrize("preview", [True, False])
    @pytest.mark.parametrize("role", ["user", "admin", "super_admin"])
    def test_without_opt_in_every_combination_stays_paper(self, live_enabled: bool, preview: bool, role: str) -> None:
        mode = resolve_automation_ccxt_execution_mode(
            role,
            connection_mainnet_opt_in=False,
            live_trading_enabled=live_enabled,
            live_trading_internal_preview=preview,
        )

        assert mode == TRADING_MODE_PAPER


class TestTheFeatureGate:
    """Gate 2, given the connection already opted in."""

    def test_global_flag_promotes_any_role_to_live(self) -> None:
        assert (
            resolve_automation_ccxt_execution_mode(
                "user",
                connection_mainnet_opt_in=True,
                live_trading_enabled=True,
                live_trading_internal_preview=False,
            )
            == TRADING_MODE_LIVE
        )

    @pytest.mark.parametrize("role", ["admin", "super_admin"])
    def test_internal_preview_promotes_staff_only(self, role: str) -> None:
        assert (
            resolve_automation_ccxt_execution_mode(
                role,
                connection_mainnet_opt_in=True,
                live_trading_enabled=False,
                live_trading_internal_preview=True,
            )
            == TRADING_MODE_LIVE
        )

    def test_internal_preview_does_not_promote_an_ordinary_user(self) -> None:
        """The preview flag is for staff on staging; a normal account must stay on paper."""
        assert (
            resolve_automation_ccxt_execution_mode(
                "user",
                connection_mainnet_opt_in=True,
                live_trading_enabled=False,
                live_trading_internal_preview=False,
            )
            == TRADING_MODE_PAPER
        )

    @pytest.mark.parametrize("role", ["user", "admin", "super_admin"])
    def test_both_flags_off_is_paper_for_everyone(self, role: str) -> None:
        assert (
            resolve_automation_ccxt_execution_mode(
                role,
                connection_mainnet_opt_in=True,
                live_trading_enabled=False,
                live_trading_internal_preview=False,
            )
            == TRADING_MODE_PAPER
        )

    def test_an_unknown_role_string_is_never_staff(self) -> None:
        """A role the system does not know must fail CLOSED, not fall through to live."""
        assert not user_may_use_live_trading(
            "definitely_not_a_role",
            live_trading_enabled=False,
            live_trading_internal_preview=True,
        )
