"""
Cross-stack contract tests: Python allowlists match web TypeScript SoT.

WHY this exists (no lazy duplication claims):
- Backend validates PATCH /auth/me with `SUPPORTED_USER_*` in shared constants.
- Product URLs and next-intl use `routing.ts`; next-themes uses `DEFAULT_THEME_MODES` / `DefaultTheme` in `app.ts`.
- There is no TS→Python codegen; CI must fail when one side adds `fr` or a new theme.

These tests read the TS files at runtime (fast: no DB, no network). Run from monorepo root.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.shared.constants.contact_inquiry import CONTACT_INQUIRY_TOPICS, MAX_MESSAGE_LENGTH
from src.shared.constants.locales import SUPPORTED_USER_LOCALES
from src.shared.constants.themes import (
    DEFAULT_PUBLIC_UI_THEME,
    SUPPORTED_USER_THEMES,
)
from tests.helpers.api_paths import REPO_ROOT


def _repo_root() -> Path:
    """tests/contracts/ → parents[4] = pulsai repo root."""
    return REPO_ROOT


def _read_text(relative_to_repo: str) -> str:
    path = _repo_root() / relative_to_repo
    if not path.is_file():
        msg = f"Missing {path}; contract tests require full monorepo checkout."
        raise AssertionError(msg)
    return path.read_text(encoding="utf-8")


def _parse_routing_locales(content: str) -> frozenset[str]:
    """Extract locale strings from `locales: ['es', 'en'],` in routing.ts."""
    match = re.search(r"locales:\s*\[([^\]]+)\]", content)
    if match is None:
        msg = "Could not find locales: [...] in routing.ts"
        raise AssertionError(msg)
    raw = match.group(1)
    parts = [p.strip().strip("'\"") for p in raw.split(",")]
    parsed = frozenset(p for p in parts if p)
    if len(parsed) == 0:
        msg = "Parsed zero locales from routing.ts"
        raise AssertionError(msg)
    return parsed


def _parse_app_locales_tuple(content: str) -> frozenset[str]:
    """Extract locale strings from `export const APP_LOCALES = ['es', 'en'] as const`."""
    match = re.search(r"export\s+const\s+APP_LOCALES\s*=\s*\[([^\]]+)\]\s+as\s+const", content)
    if match is None:
        msg = "Could not find APP_LOCALES = [...] as const in locale-registry.ts"
        raise AssertionError(msg)
    body = match.group(1)
    locales = frozenset(value for value in re.findall(r"'([^']+)'", body) if value)
    if len(locales) == 0:
        msg = "Parsed zero locales from locale-registry.ts"
        raise AssertionError(msg)
    return locales


def _parse_web_locales_with_fallback(*, routing_content: str, locale_registry_content: str) -> frozenset[str]:
    """
    Read frontend locale SoT.

    Prefer literal `locales: [...]` in `routing.ts` for legacy compatibility; if routing delegates to
    `APP_LOCALES`, read the tuple from `locale-registry.ts`.
    """
    try:
        return _parse_routing_locales(routing_content)
    except AssertionError:
        return _parse_app_locales_tuple(locale_registry_content)


def _parse_default_theme_union(content: str) -> frozenset[str]:
    """Extract union members from `export type DefaultTheme = 'a' | 'b' | 'c';` (legacy)."""
    match = re.search(r"export\s+type\s+DefaultTheme\s*=\s*(.+?);", content, re.DOTALL)
    if match is None:
        msg = "Could not find export type DefaultTheme in app.ts"
        raise AssertionError(msg)
    rhs = match.group(1)
    members = re.findall(r"'([^']+)'", rhs)
    if len(members) == 0:
        msg = "Could not parse DefaultTheme string literals in app.ts"
        raise AssertionError(msg)
    return frozenset(members)


def _parse_default_theme_modes_array(content: str) -> frozenset[str]:
    """
    Extract themes from `export const DEFAULT_THEME_MODES = ['light', ...] as const`.

    This is the current FE SoT when ``DefaultTheme`` is ``(typeof DEFAULT_THEME_MODES)[number]``.
    """
    match = re.search(
        r"export\s+const\s+DEFAULT_THEME_MODES\s*=\s*\[([^\]]+)\]\s+as\s+const",
        content,
    )
    if match is None:
        msg = "Could not find DEFAULT_THEME_MODES = [...] as const in app.ts"
        raise AssertionError(msg)
    body = match.group(1)
    members = re.findall(r"'([^']+)'", body)
    if len(members) == 0:
        msg = "Could not parse DEFAULT_THEME_MODES string literals in app.ts"
        raise AssertionError(msg)
    return frozenset(members)


def _parse_supported_user_themes_from_app_ts(content: str) -> frozenset[str]:
    """
    Theme allowlist for cross-stack contract.

    Prefer ``DEFAULT_THEME_MODES`` (tuple SoT); fall back to literal union if present.
    """
    try:
        return _parse_default_theme_modes_array(content)
    except AssertionError:
        return _parse_default_theme_union(content)


def _parse_app_config_default_theme_value(content: str) -> str:
    """Read APP_CONFIG.ui.defaultTheme string (must match GET /config ui.default_theme)."""
    match = re.search(r"defaultTheme:\s*'([^']+)'\s+as\s+DefaultTheme", content)
    if match is None:
        msg = "Could not find defaultTheme: '...' as DefaultTheme in app.ts"
        raise AssertionError(msg)
    return match.group(1)


def _parse_contact_message_max_length(content: str) -> int:
    """Read CONTACT_MESSAGE_MAX_LENGTH from apps/web/src/types/contact.ts."""
    match = re.search(r"export const CONTACT_MESSAGE_MAX_LENGTH = (\d+);", content)
    if match is None:
        msg = "Could not find CONTACT_MESSAGE_MAX_LENGTH in types/contact.ts"
        raise AssertionError(msg)
    return int(match.group(1))


def _parse_contact_topics_tuple(content: str) -> tuple[str, ...]:
    """
    Parse CONTACT_TOPICS array order from apps/web/src/types/contact.ts.

    Must match CONTACT_INQUIRY_TOPICS as a set; order is a UX contract for selects.
    """
    match = re.search(
        r"export const CONTACT_TOPICS = \[([\s\S]*?)\]\s+as const",
        content,
    )
    if match is None:
        msg = "Could not find CONTACT_TOPICS = [...] as const in types/contact.ts"
        raise AssertionError(msg)
    body = match.group(1)
    topics = re.findall(r"'([^']+)'", body)
    if len(topics) == 0:
        msg = "Parsed zero topic strings from CONTACT_TOPICS in types/contact.ts"
        raise AssertionError(msg)
    return tuple(topics)


@pytest.mark.unit
def test_supported_user_locales_match_next_intl_routing() -> None:
    """Profile locale allowlist must match `defineRouting({ locales })` (order-independent)."""
    routing_ts = _read_text("apps/web/src/i18n/routing.ts")
    locale_registry_ts = _read_text("apps/web/src/i18n/locale-registry.ts")
    from_routing = _parse_web_locales_with_fallback(
        routing_content=routing_ts,
        locale_registry_content=locale_registry_ts,
    )
    assert from_routing == SUPPORTED_USER_LOCALES, (
        "SUPPORTED_USER_LOCALES must match apps/web/src/i18n/routing.ts `locales`. "
        f"backend={sorted(SUPPORTED_USER_LOCALES)} routing={sorted(from_routing)}"
    )


@pytest.mark.unit
def test_supported_user_themes_match_app_ts_default_theme_type() -> None:
    """Theme allowlist must match `DEFAULT_THEME_MODES` / `DefaultTheme` in app.ts (next-themes)."""
    app_ts = _read_text("apps/web/src/config/app.ts")
    from_app = _parse_supported_user_themes_from_app_ts(app_ts)
    assert from_app == SUPPORTED_USER_THEMES, (
        "SUPPORTED_USER_THEMES must match DEFAULT_THEME_MODES (or DefaultTheme union) in app.ts. "
        f"backend={sorted(SUPPORTED_USER_THEMES)} app_ts={sorted(from_app)}"
    )


@pytest.mark.unit
def test_parse_supported_user_themes_reads_default_theme_modes_tuple() -> None:
    """REGRESSION: When DefaultTheme is (typeof DEFAULT_THEME_MODES)[number], parse the tuple."""
    snippet = """
    export const DEFAULT_THEME_MODES = ['light', 'dark', 'system'] as const;
    export type DefaultTheme = (typeof DEFAULT_THEME_MODES)[number];
    """
    assert _parse_supported_user_themes_from_app_ts(snippet) == frozenset({"light", "dark", "system"})


@pytest.mark.unit
def test_parse_supported_user_themes_legacy_union_fallback() -> None:
    """Older app.ts: literal union without DEFAULT_THEME_MODES."""
    snippet = "export type DefaultTheme = 'light' | 'dark' | 'system';"
    assert _parse_supported_user_themes_from_app_ts(snippet) == frozenset({"light", "dark", "system"})


@pytest.mark.unit
def test_parse_web_locales_falls_back_to_app_locales_tuple() -> None:
    """REGRESSION: routing may delegate locale ids to APP_LOCALES in locale-registry.ts."""
    routing_snippet = """
    export const routing = defineRouting({
      locales: APP_LOCALES,
      defaultLocale: DEFAULT_LOCALE,
    });
    """
    locale_registry_snippet = "export const APP_LOCALES = ['es', 'en'] as const;"
    assert _parse_web_locales_with_fallback(
        routing_content=routing_snippet,
        locale_registry_content=locale_registry_snippet,
    ) == frozenset({"es", "en"})


@pytest.mark.unit
def test_public_ui_default_theme_matches_app_config() -> None:
    """GET /config `ui.default_theme` default must match APP_CONFIG.ui.defaultTheme."""
    app_ts = _read_text("apps/web/src/config/app.ts")
    fe_default = _parse_app_config_default_theme_value(app_ts)
    assert fe_default == DEFAULT_PUBLIC_UI_THEME, (
        f"DEFAULT_PUBLIC_UI_THEME must match APP_CONFIG.ui.defaultTheme in app.ts. backend={DEFAULT_PUBLIC_UI_THEME!r} app_ts={fe_default!r}"
    )


@pytest.mark.unit
def test_contact_inquiry_topics_match_types_contact_ts() -> None:
    """CONTACT_INQUIRY_TOPICS must match CONTACT_TOPICS in apps/web/src/types/contact.ts (set equality)."""
    contact_ts = _read_text("apps/web/src/types/contact.ts")
    from_ts = frozenset(_parse_contact_topics_tuple(contact_ts))
    assert from_ts == CONTACT_INQUIRY_TOPICS, (
        f"CONTACT_INQUIRY_TOPICS must match CONTACT_TOPICS in types/contact.ts. backend={sorted(CONTACT_INQUIRY_TOPICS)} ts={sorted(from_ts)}"
    )


@pytest.mark.unit
def test_contact_inquiry_max_message_length_matches_types_contact_ts() -> None:
    """MAX_MESSAGE_LENGTH must match CONTACT_MESSAGE_MAX_LENGTH in web types."""
    contact_ts = _read_text("apps/web/src/types/contact.ts")
    from_ts = _parse_contact_message_max_length(contact_ts)
    assert from_ts == MAX_MESSAGE_LENGTH, (
        f"MAX_MESSAGE_LENGTH must match CONTACT_MESSAGE_MAX_LENGTH in types/contact.ts. backend={MAX_MESSAGE_LENGTH} ts={from_ts}"
    )
