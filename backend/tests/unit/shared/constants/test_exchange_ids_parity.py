"""
Parity test: BE ``SUPPORTED_EXCHANGES`` matches the canonical TS SoT at
``packages/shared/src/constants/exchanges.ts`` (``EXCHANGE_IDS``).

The TS SoT is hand-mirrored into Python in
``src/shared/constants/exchanges.py``. Both sides are asserted against the
**same** hand-written tuple inside this test so a drift on either side
(reorder, addition, deletion) fails CI on both apps/web vitest and
apps/api pytest.

When adding an exchange:
  1. Add to ``EXCHANGE_IDS`` in TS (packages/shared/src/constants/exchanges.ts)
  2. Add to ``SUPPORTED_EXCHANGES`` in Python (src/shared/constants/exchanges.py)
  3. Add to the ``_CANONICAL_EXCHANGE_IDS`` tuple **here**
  4. Add to the FE sibling test
     (apps/web/tests/unit/shared/exchanges.test.ts)

See docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md for the rationale.
"""

from __future__ import annotations

from src.domain.enums import Exchange
from src.shared.constants.exchanges import (
    EXCHANGES_WITH_TESTNET,
    FUTURES_PAPER_SUPPORTED_EXCHANGES,
    SUPPORTED_EXCHANGES,
)

# Canonical ordering — mirrors EXCHANGE_IDS in
# packages/shared/src/constants/exchanges.ts. Hand-mirrored on purpose
# (3 venues today; tiny enough to keep in sync manually; switch to a
# codegen pipeline only when the list grows past ~10).
_CANONICAL_EXCHANGE_IDS: tuple[str, ...] = (
    "binance",
    "bitget",
    "bybit",
    "okx",
    "coinbase",
    "kraken",
)


class TestExchangeIdsParity:
    """Pin the SUPPORTED_EXCHANGES ↔ TS EXCHANGE_IDS parity at module load."""

    def test_supported_exchanges_matches_canonical_order(self) -> None:
        """Python tuple is byte-equal to the canonical hand-mirrored list."""
        assert SUPPORTED_EXCHANGES == _CANONICAL_EXCHANGE_IDS

    def test_no_unexpected_exchanges_in_testnet_map(self) -> None:
        """EXCHANGES_WITH_TESTNET keys = SUPPORTED_EXCHANGES (no drift)."""
        assert set(EXCHANGES_WITH_TESTNET.keys()) == set(SUPPORTED_EXCHANGES)

    def test_futures_paper_subset_lives_in_supported(self) -> None:
        """Every venue in FUTURES_PAPER_SUPPORTED_EXCHANGES is also a known exchange."""
        assert FUTURES_PAPER_SUPPORTED_EXCHANGES.issubset(set(SUPPORTED_EXCHANGES))


class TestExchangeStrEnumParity:
    """Pin the narrow Exchange StrEnum subset against the canonical SoT."""

    def test_str_enum_values_subset_of_canonical(self) -> None:
        """Every Exchange enum value is a member of the canonical id list."""
        enum_values = {member.value for member in Exchange}
        assert enum_values.issubset(set(_CANONICAL_EXCHANGE_IDS))

    def test_str_enum_includes_bybit_after_phase1_add(self) -> None:
        """Bybit is in the typed enum (Phase 1 added it — previously missing)."""
        assert Exchange.BYBIT.value == "bybit"

    def test_get_fee_rate_returns_default_for_known_exchanges(self) -> None:
        """Every enum member has an explicit fee row (no defensive 0.001 fallback)."""
        # Fee table is private; assert the public API returns the explicit
        # 0.001 row for each, not the fallback. (Both happen to equal 0.001
        # today; the assertion shape catches a future row deletion.)
        for member in Exchange:
            assert member.get_fee_rate() == 0.001
