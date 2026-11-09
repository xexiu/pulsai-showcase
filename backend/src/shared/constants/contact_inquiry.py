"""Allowed contact form topic values (SoT for API + DB check constraint)."""

from typing import Final

# Public contact reasons — keep in sync with web `contact` i18n / Valibot enum.
CONTACT_INQUIRY_TOPICS: Final[frozenset[str]] = frozenset(
    {
        "general",
        "support",
        "partnership",
        "press",
        "other",
    }
)

MAX_MESSAGE_LENGTH: Final[int] = 8000
