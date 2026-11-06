"""
User theme preference values (`users.settings["theme"]`, PATCH /auth/me/settings).

Cross-stack contract (update together when adding a variant):
- next-themes: https://github.com/pacocoursey/next-themes — attribute values `light` | `dark` | `system`
- Frontend type SoT: `apps/web/src/config/app.ts` (`DefaultTheme`)

This module is the **backend** SoT: `UserTheme` typing, runtime allowlist, and defaults.
Do not redefine `Literal["light", "dark", "system"]` elsewhere in apps/api.
"""

from typing import Literal

# Membership checks; OpenAPI may still list enum from Literal on models.
SUPPORTED_USER_THEMES: frozenset[str] = frozenset({"light", "dark", "system"})

UserTheme = Literal["light", "dark", "system"]

# Persisted default for new users (`User.settings` JSON).
DEFAULT_USER_THEME: UserTheme = "system"

# Public config endpoint default (`GET /config` → `ui.default_theme`); may differ per env.
DEFAULT_PUBLIC_UI_THEME: UserTheme = "dark"
