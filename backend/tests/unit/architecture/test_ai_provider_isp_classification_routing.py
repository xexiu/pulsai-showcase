"""Architectural fitness function: classification callers MUST use the lean path.

TPM RATIONALE
=============
The AI/LLM provider boundary has two distinct calling paths:

* HEAVY path — ``explain_signal_with_runtime_fallback`` — injects the
  full trading ``SYSTEM_PROMPT`` (~1 500 tokens) plus a localized disclaimer.
  Reserved for user-facing signal explanations (API endpoints, Telegram bot).

* LEAN path — ``classify_text_with_news_fallback`` / ``AIProvider.classify_text``
  — accepts a caller-supplied system prompt with NO trading ``SYSTEM_PROMPT``
  and NO disclaimer (~180 tokens/call).  Designed for short classification
  tasks (e.g. news-impact sentiment).

On Groq's free tier (~6 000 TPM):
  heavy  → ~3.5 classification calls / min (SYSTEM_PROMPT alone costs ~1 500 tok)
  lean   → ~33 classification calls / min (~9x headroom)

Routing a classification caller through the heavy path silently exhausts the
free-tier TPM budget, causing cascading 429s for ALL LLM features.

AUDIT (verified healthy 2026-06-19)
====================================
The only production classification caller — ``headline_impact_classification``
— correctly uses the lean path.  This test LOCKS that invariant so a future
change cannot silently reroute a classification caller onto the heavy path.

FAILURE MODE
============
If this test starts failing it means one of:
  1. A classification module now imports ``explain_signal_with_runtime_fallback``
     or references the heavy ``SYSTEM_PROMPT`` constant — stop and investigate
     before merging.
  2. A new classification module was added without routing through
     ``classify_text_with_news_fallback`` — add it to the lean-path allowlist
     AND assert it is absent from the heavy-path set.

DO NOT add an exception here without a documented architect decision that
explains why a classification caller can tolerate 4x the token cost.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Final

from tests.helpers.api_paths import API_ROOT

# ---------------------------------------------------------------------------
# Repo layout constants
# ---------------------------------------------------------------------------

_SRC_ROOT: Final[Path] = API_ROOT / "src"

# The classification module under test.
_CLASSIFICATION_MODULE: Final[str] = "src.infrastructure.sentiment.headline_impact_classification"
_CLASSIFICATION_FILE: Final[Path] = _SRC_ROOT / "infrastructure" / "sentiment" / "headline_impact_classification.py"

# Heavy-path symbol names that must NOT appear in classification modules.
_HEAVY_SYMBOLS: Final[frozenset[str]] = frozenset(
    {
        "explain_signal_with_runtime_fallback",
        "explain_signal",  # the abstract method on AIProvider (heavy path)
    }
)

# The trading SYSTEM_PROMPT is defined and re-exported here; a classification
# module must never import it (it would signal routing onto the heavy path).
_HEAVY_PROMPT_MODULES: Final[frozenset[str]] = frozenset(
    {
        "src.infrastructure.ai.ai_provider_base",
        "src.infrastructure.ai.providers",
    }
)
_HEAVY_PROMPT_SYMBOL: Final[str] = "SYSTEM_PROMPT"

# Lean-path symbol that MUST be present in classification callers.
_LEAN_SYMBOL: Final[str] = "classify_text_with_news_fallback"

# ---------------------------------------------------------------------------
# Heavy-path caller allowlist + lean-prompt budget (structural TPM/cost guards)
# ---------------------------------------------------------------------------

# The expensive path, as referenced for the repo-wide caller scan (Test 6). A distinct
# name from _HEAVY_SYMBOLS (Tests 1-3): this is the single public entrypoint scanned
# across src/, not the full symbol-exclusion set.
_HEAVY_CALLER_SCAN_SYMBOL: Final[str] = "explain_signal_with_runtime_fallback"

# The module that DEFINES + re-exports the heavy path (excluded from the caller scan).
_HEAVY_PATH_DEFINITION_FILE: Final[str] = "infrastructure/ai/providers.py"

# Closed allowlist (src-relative POSIX paths) of production modules permitted to call
# the heavy path. Adding a caller here is a DELIBERATE act that must be justified — a
# short classification caller belongs on the lean path, not here.
_HEAVY_PATH_ALLOWED_CALLERS: Final[frozenset[str]] = frozenset(
    {
        "api/v1/endpoints/ai.py",  # /ai explain endpoints (stream + single + multi-TF)
        "infrastructure/telegram/telegram_explain_handlers.py",  # /explain + /confluence bot commands
    }
)

# The lean-prompt size budget lives in src (its SoT — news_impact.py owns "the token
# budget"); Test 7 imports it. No test-local copy (avoids a duplicated magic number).


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_names(tree: ast.Module) -> set[str]:
    """Return every name imported at module level (from … import name, import name)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _all_name_references(tree: ast.Module) -> set[str]:
    """Return every Name / Attribute id referenced anywhere in the module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _from_import_sources(tree: ast.Module) -> dict[str, str]:
    """Map imported name → source module for all ``from X import Y`` statements."""
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                mapping[local] = node.module
    return mapping


def _src_files_referencing(symbol: str) -> set[str]:
    """Return src-relative POSIX paths of every ``src/`` ``.py`` file that imports or
    references ``symbol`` (AST-confirmed, so a docstring mention does not count).

    A cheap substring pre-filter skips the AST parse for files that can't match, so the
    repo-wide scan only parses the handful of files that actually reference the symbol.

    Limitation: a deliberately obfuscated ``getattr(module, "<symbol>")(...)`` call is
    not detected (no AST identifier node carries the name). That is an adversarial write,
    not the accidental-misrouting threat this fitness function targets.
    """
    hits: set[str] = set()
    for path in _SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if symbol not in text:  # pre-filter: avoid parsing files with no chance of a match
            continue
        tree = ast.parse(text, filename=str(path))
        referenced = _imported_names(tree) | _all_name_references(tree)
        # Also match the ORIGINAL imported name so an aliased import
        # (``from ... import explain_signal_with_runtime_fallback as foo``) can't evade
        # the guard; docstring/string mentions are still ignored (not AST identifiers).
        for node in ast.walk(tree):
            if isinstance(node, (ast.ImportFrom, ast.Import)):
                referenced |= {alias.name for alias in node.names}
        if symbol in referenced:
            hits.add(path.relative_to(_SRC_ROOT).as_posix())
    return hits


# ---------------------------------------------------------------------------
# Test 1 — classification module does NOT reference the heavy path symbols
# ---------------------------------------------------------------------------


def test_headline_classification_does_not_import_heavy_path() -> None:
    """Assert that headline_impact_classification does not import explain_signal_with_runtime_fallback.

    Routing a classification caller through the heavy path would inject the
    full trading SYSTEM_PROMPT (~1 500 tokens) and disclaimer, reducing
    free-tier throughput from ~33 calls/min to ~3.5 calls/min (~9x regression).

    This test reads the module's AST statically — no import side-effects.
    """
    tree = _parse_ast(_CLASSIFICATION_FILE)
    imported = _imported_names(tree)
    all_refs = _all_name_references(tree)

    violations = _HEAVY_SYMBOLS & (imported | all_refs)
    assert not violations, (
        f"headline_impact_classification references heavy-path symbol(s): {violations}. "
        "Classification callers MUST use classify_text_with_news_fallback (lean path). "
        "Routing through the heavy path blows free-tier TPM (~9x overhead). "
        "See test module docstring for the full rationale."
    )


# ---------------------------------------------------------------------------
# Test 2 — classification module does NOT import the heavy SYSTEM_PROMPT
# ---------------------------------------------------------------------------


def test_headline_classification_does_not_import_trading_system_prompt() -> None:
    """Assert that SYSTEM_PROMPT (trading assistant constant) is absent from the classification module.

    The classification path uses NEWS_IMPACT_SYSTEM_PROMPT (lean, ~180 tok).
    Importing SYSTEM_PROMPT from ai_provider_base or providers signals that
    a classification call has leaked onto the heavy explain-signal path.
    """
    tree = _parse_ast(_CLASSIFICATION_FILE)
    sources = _from_import_sources(tree)

    # Check that SYSTEM_PROMPT is not imported from any heavy-path module.
    for local_name, source_module in sources.items():
        if local_name == _HEAVY_PROMPT_SYMBOL and source_module in _HEAVY_PROMPT_MODULES:
            raise AssertionError(
                f"headline_impact_classification imports SYSTEM_PROMPT from "
                f"'{source_module}'. This is the trading-assistant heavy prompt "
                "(~1 500 tokens) — classification callers must use "
                "NEWS_IMPACT_SYSTEM_PROMPT from src.shared.constants.news_impact."
            )

    # Defensive: also catch bare 'SYSTEM_PROMPT' anywhere as a name reference
    # (could be accessed via a wildcard import or an aliased module).
    all_refs = _all_name_references(tree)
    assert _HEAVY_PROMPT_SYMBOL not in all_refs, (
        f"headline_impact_classification references '{_HEAVY_PROMPT_SYMBOL}' "
        "(the heavy trading-assistant prompt). Classification callers must use "
        "NEWS_IMPACT_SYSTEM_PROMPT. "
        "See test module docstring for the full rationale."
    )


# ---------------------------------------------------------------------------
# Test 3 — classification module DOES use the lean path
# ---------------------------------------------------------------------------


def test_headline_classification_uses_lean_path() -> None:
    """Assert that headline_impact_classification imports and calls classify_text_with_news_fallback.

    This is the positive assertion — the lean path must be actively used,
    not merely 'not the heavy one'.  A future refactor that removes the
    lean-path call entirely (e.g. replaces with a direct HTTP call that
    bypasses the TPM-aware chain) should also fail this test.
    """
    tree = _parse_ast(_CLASSIFICATION_FILE)
    imported = _imported_names(tree)
    all_refs = _all_name_references(tree)

    assert _LEAN_SYMBOL in imported or _LEAN_SYMBOL in all_refs, (
        f"headline_impact_classification no longer references '{_LEAN_SYMBOL}'. "
        "Either the lean path was removed (regression) or the caller switched "
        "to a different mechanism — verify it still respects the TPM contract "
        "before merging. See test module docstring for rationale."
    )


# ---------------------------------------------------------------------------
# Test 4 — lean-path function is correctly wired: no SYSTEM_PROMPT injection
# ---------------------------------------------------------------------------


def test_classify_text_with_news_fallback_does_not_pass_trading_system_prompt() -> None:
    """Assert that classify_text_with_news_fallback does not inject the trading SYSTEM_PROMPT.

    The lean-path orchestrator (providers.classify_text_with_news_fallback) must
    pass the caller-supplied ``system`` argument verbatim to each provider's
    ``classify_text()`` method — it must NOT substitute or prepend the heavy
    trading SYSTEM_PROMPT.  This is verified by inspecting the function's source.
    """
    import src.infrastructure.ai.providers as providers_module

    fn = providers_module.classify_text_with_news_fallback
    source = inspect.getsource(fn)

    # The lean orchestrator must NOT reference SYSTEM_PROMPT in its body.
    assert "SYSTEM_PROMPT" not in source, (
        "classify_text_with_news_fallback references 'SYSTEM_PROMPT' in its body. "
        "The lean path must pass the caller-supplied system prompt verbatim — "
        "injecting the heavy trading SYSTEM_PROMPT here would silently route all "
        "classification calls through the 4x token overhead path. "
        "See test module docstring for the full TPM rationale."
    )


# ---------------------------------------------------------------------------
# Test 5 — the classification file actually exists (allowlist hygiene)
# ---------------------------------------------------------------------------


def test_classification_module_file_exists() -> None:
    """Sanity guard: the file the other tests inspect must exist on disk.

    If the module is renamed or moved, the AST-based tests above would pass
    vacuously (file not found = no violations found).  This explicit check
    prevents silent false-passes after a rename.
    """
    assert _CLASSIFICATION_FILE.exists(), (
        f"Classification module not found at {_CLASSIFICATION_FILE}. "
        "If the file was renamed or moved, update _CLASSIFICATION_FILE in this "
        "test and verify the new path still uses the lean path."
    )


# ---------------------------------------------------------------------------
# Test 5b — the heavy-path definition file exists (exclusion hygiene)
# ---------------------------------------------------------------------------


def test_heavy_path_definition_file_exists() -> None:
    """Sanity guard for Test 6's exclusion set.

    Test 6 subtracts ``_HEAVY_PATH_DEFINITION_FILE`` from the scanned callers. If
    ``providers.py`` is renamed without updating that constant, the subtraction silently
    no-ops and Test 6 fails with a misleading 'unapproved caller' pointing at the
    definition module itself. Pin the path so the failure is honest.
    """
    assert (_SRC_ROOT / _HEAVY_PATH_DEFINITION_FILE).exists(), (
        f"Heavy-path definition file not found at {_HEAVY_PATH_DEFINITION_FILE}. "
        "If providers.py was moved/renamed, update _HEAVY_PATH_DEFINITION_FILE."
    )


# ---------------------------------------------------------------------------
# Test 6 — the heavy path has a CLOSED caller allowlist (structural safety)
# ---------------------------------------------------------------------------


def test_heavy_explain_path_caller_set_is_a_closed_allowlist() -> None:
    """The expensive explain_signal path must have a CLOSED set of callers.

    Tests 1-3 guard ONE known classification module by name - that is still a
    'remember to add a per-module test' behavior. This guard is structural: it
    scans ALL of ``src/`` and fails if ANY module outside the approved allowlist
    calls the heavy path, so a NEW classification caller cannot silently route
    onto it (the recurring free-tier TPM hazard). Adding a caller requires a
    deliberate edit to ``_HEAVY_PATH_ALLOWED_CALLERS`` with a justification.
    """
    callers = _src_files_referencing(_HEAVY_CALLER_SCAN_SYMBOL) - {_HEAVY_PATH_DEFINITION_FILE}

    unauthorized = callers - _HEAVY_PATH_ALLOWED_CALLERS
    assert not unauthorized, (
        f"Unapproved caller(s) of the heavy {_HEAVY_CALLER_SCAN_SYMBOL!r} path: {sorted(unauthorized)}. "
        "The heavy path injects the full trading SYSTEM_PROMPT (~1500 tok) and is reserved for "
        "user-facing explanation surfaces. If this is a short classification, route it through the "
        "lean classify_text_with_news_fallback path instead; if it is a legitimate explanation "
        "surface, add it to _HEAVY_PATH_ALLOWED_CALLERS with a justification."
    )


# ---------------------------------------------------------------------------
# Test 7 — the lean classification prompt stays within its cost budget
# ---------------------------------------------------------------------------


def test_lean_news_impact_prompt_stays_within_budget() -> None:
    """The lean classification system prompt must stay small (cost-as-structure).

    The whole point of the lean path is a tiny system prompt. If a future edit
    bloats NEWS_IMPACT_SYSTEM_PROMPT toward the heavy SYSTEM_PROMPT's size, the
    free-tier TPM hazard returns even though the call still uses the 'lean' path.
    This pins the prompt under a budget so cost can't silently regress.
    """
    from src.shared.constants.news_impact import (
        NEWS_IMPACT_SYSTEM_PROMPT,
        NEWS_IMPACT_SYSTEM_PROMPT_MAX_CHARS,
    )

    size = len(NEWS_IMPACT_SYSTEM_PROMPT)
    assert size <= NEWS_IMPACT_SYSTEM_PROMPT_MAX_CHARS, (
        f"NEWS_IMPACT_SYSTEM_PROMPT is {size} chars, over the lean budget of "
        f"{NEWS_IMPACT_SYSTEM_PROMPT_MAX_CHARS}. The lean classification prompt must stay small to "
        "keep free-tier TPM cost low. If the growth is justified, raise "
        "NEWS_IMPACT_SYSTEM_PROMPT_MAX_CHARS (in src/shared/constants/news_impact.py) deliberately "
        "and confirm it stays well under the heavy SYSTEM_PROMPT size."
    )
