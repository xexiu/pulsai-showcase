"""The frontend's symbol list must not drift from the backend's (2026-09-11).

Measured the day this was written: backend ``supported_symbols`` held 5 symbols, the shared
``TradingSymbol`` union 5, the Valibot ``TradingSymbolSchema`` 5, and the ``TRADING_SYMBOLS``
fallback 3 (BNB and XRP commented out as "future expansion"). Four hand-kept copies of one list,
one already drifted. Owner, same day: "we should add our symbols/coins as SoT, centralized. If
someone adds a new coin/symbol, the news MUST include it also".

Same failure and same mechanism as ``test_timeframe_frontend_parity.py``: a TypeScript union is
COMPILE-TIME, so ``packages/shared`` must keep a static copy. The copy is allowed to exist only
as ONE list that everything else derives from, and this test is what stops it rotting.
"""

from __future__ import annotations

import re

from src.infrastructure.config.settings_sections.settings_trading import SettingsTradingMixin
from src.shared.constants.trading import DEFAULT_SUPPORTED_SYMBOL_VALUES
from tests.helpers.api_paths import REPO_ROOT

_SHARED = REPO_ROOT / "packages" / "shared" / "src"
_REGISTRY_TS = _SHARED / "constants" / "symbol-registry.ts"
_COMMON_TS = _SHARED / "types" / "common.ts"
_TRADING_TS = _SHARED / "constants" / "trading.ts"
_SIGNALS_TS = _SHARED / "validators" / "signals.ts"
_REGISTRY_NAME = "DEFAULT_SUPPORTED_SYMBOLS"
_SYMBOL_LITERAL = re.compile(r"'[A-Z0-9]+/[A-Z0-9]+'")


def _statement(text: str, opener: str) -> str:
    """Source from ``opener`` up to the terminating semicolon."""
    start = text.index(opener)
    return text[start : text.index(";", start)]


def test_the_guard_can_actually_see_the_shared_package() -> None:
    """Guard the guard: if these paths stop resolving, every check below is vacuous."""
    for path in (_REGISTRY_TS, _COMMON_TS, _TRADING_TS, _SIGNALS_TS):
        assert path.is_file(), f"shared file not found at {path}"


def test_the_settings_default_is_built_from_the_backend_constant() -> None:
    assert SettingsTradingMixin.supported_symbols == ",".join(DEFAULT_SUPPORTED_SYMBOL_VALUES)


def test_the_shared_registry_matches_the_backend_list_in_order() -> None:
    """Order matters: the first symbol is the product default everywhere."""
    registry = _REGISTRY_TS.read_text(encoding="utf-8")
    members = re.findall(r"'([^']+)'", _statement(registry, f"export const {_REGISTRY_NAME}"))

    assert members == list(DEFAULT_SUPPORTED_SYMBOL_VALUES), "packages/shared symbol-registry.ts has drifted from DEFAULT_SUPPORTED_SYMBOL_VALUES"


def test_the_trading_symbol_type_is_derived_not_retyped() -> None:
    statement = _statement(_COMMON_TS.read_text(encoding="utf-8"), "export type TradingSymbol")

    assert _REGISTRY_NAME in statement, "TradingSymbol must be derived from the symbol registry"
    assert not _SYMBOL_LITERAL.search(statement), "TradingSymbol re-types symbol literals instead of deriving them"


def test_the_fallback_list_is_derived_not_retyped() -> None:
    """THE REGRESSION: this fallback listed 3 symbols while the backend served 5."""
    statement = _statement(_TRADING_TS.read_text(encoding="utf-8"), "export const TRADING_SYMBOLS")

    assert _REGISTRY_NAME in statement, "TRADING_SYMBOLS must be derived from the symbol registry"
    assert not _SYMBOL_LITERAL.search(statement), "TRADING_SYMBOLS re-types symbol literals instead of deriving them"


def test_the_validator_is_derived_not_retyped() -> None:
    statement = _statement(_SIGNALS_TS.read_text(encoding="utf-8"), "export const TradingSymbolSchema")

    assert _REGISTRY_NAME in statement, "TradingSymbolSchema must be derived from the symbol registry"
    assert not _SYMBOL_LITERAL.search(statement), "TradingSymbolSchema re-types symbol literals instead of deriving them"
