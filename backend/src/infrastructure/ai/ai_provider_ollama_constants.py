"""Constants for the local Ollama AI provider.

Extracted from ``ai_provider_ollama.py`` (sibling pattern already used by
``src/infrastructure/ml/model_storage_constants.py`` and
``src/application/billing/admin_billing_constants.py``: a feature-local ``_constants`` module
next to its one consumer, rather than centralising into ``src/shared/constants`` for a value
nothing else reads yet).

WHY A SEPARATE FILE: ``architect_standards_guard.py`` (PreToolUse hard-rule gate) bans a literal
URL anywhere under ``src/infrastructure/ai/*`` outside a path containing "constants" or
"settings" — the guard's own docstring: "Tests, scripts, migrations, and constants/settings
modules are exempt by design — a constants module's whole job is to hold the literals everything
else must not inline." A module-level ``Final`` constant declared directly inside
``ai_provider_ollama.py`` still trips it (the check is path-based, not "is this already named").
"""

from __future__ import annotations

from typing import Final

#: Env var naming the local Ollama server. No vendor SDK exists to supply a default for a
#: self-hosted server, so this module owns both the variable name and the fallback value.
OLLAMA_BASE_URL_ENV_VAR: Final[str] = "OLLAMA_BASE_URL"

#: Confirmed reachable during development: `curl http://127.0.0.1:11434/api/version` -> 0.33.3.
DEFAULT_OLLAMA_BASE_URL: Final[str] = "http://127.0.0.1:11434"

#: Model id used when neither the constructor nor a per-call override names one.
DEFAULT_OLLAMA_MODEL: Final[str] = "qwen2.5:14b-instruct"

__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_OLLAMA_MODEL",
    "OLLAMA_BASE_URL_ENV_VAR",
]
