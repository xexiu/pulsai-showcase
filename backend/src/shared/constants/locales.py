"""
Supported user profile locale codes (stored on `users.locale`, PATCH /auth/me).

NOT a magic string scattered in Pydantic — single import for validation + OpenAPI.

Cross-stack contract (must stay in sync when adding e.g. `fr`):
- Product SoT for URL segments & next-intl: `apps/web/src/i18n/routing.ts` (`locales` array).
- Also update: `apps/web/src/i18n/config.ts` (LOCALE_NAMES, LOCALE_HREFLANG), message files,
  and any profile UI that lists locales.

This module is the **backend** SoT only. There is no runtime import from the TS repo;
when you add a locale, update **both** routing.ts and `SUPPORTED_USER_LOCALES` below
(or add a codegen/check in CI later).
"""

# Match the set in `routing.locales` (order independent for membership checks).
SUPPORTED_USER_LOCALES: frozenset[str] = frozenset({"en", "es"})

# Product/user-profile default locale when caller input is absent or invalid.
DEFAULT_USER_LOCALE: str = "es"

# Default locale for API explain/streaming when caller does not specify.
DEFAULT_EXPLAIN_LOCALE: str = "es"


def resolve_user_locale(preferred_locale: str | None, *, fallback_locale: str = DEFAULT_USER_LOCALE) -> str:
    """Resolve a persisted user locale from caller input with a safe supported fallback."""
    if preferred_locale in SUPPORTED_USER_LOCALES:
        return preferred_locale
    if fallback_locale in SUPPORTED_USER_LOCALES:
        return fallback_locale
    return DEFAULT_USER_LOCALE
