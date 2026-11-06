"""Ollama AI Provider — talks to a LOCAL Ollama server over its native ``/api/chat`` endpoint.

WHY NOT ``KeyedAIProviderMixin``? That mixin's whole contract is "resolve an API key from
settings, treat an empty key as a configuration error, build a vendor SDK client." Ollama has no
key at all — it is an unauthenticated local server — so "configured" cannot mean "a key is
present"; it has to mean "the server answers." Reusing the mixin would either fake a key
requirement that does not exist, or leave ``is_configured()`` permanently True regardless of
whether anything is actually listening on the port. Construction is orthogonal to authentication
(the mixin's own docstring makes that split explicit for the vision/text ABCs); this provider
simply has nothing to plug into that seam.

REUSE-AUDIT: considered ``src/infrastructure/config`` settings for the base URL — the pattern
every keyed provider follows (e.g. ``settings.groq_api_key``). Not adding a field there: this
provider's permitted edit scope is ``src/infrastructure/ai/*`` and ``tests/unit/infrastructure/
ai/*`` only, and ``src/infrastructure/config`` is outside it. The env-var-with-default constants
now live in the sibling ``ai_provider_ollama_constants.py`` (see that file's docstring for why a
separate module was needed) — that satisfies "no hardcoded strings/URLs" without an out-of-scope
edit; if Ollama becomes a first-class runtime provider (added to a fallback chain in
``providers.py``), promoting the base URL to a real settings field belongs with that later
decision, not this one. Also considered ``src.shared.constants._env_resolvers`` — it has no
string resolver (only bool/int/float), so reusing it would mean adding one there, an equally
out-of-scope edit.

Uses ``httpx`` (already a declared project dependency, ``httpx>=0.28.1`` in pyproject.toml) rather
than ``requests`` (present in this venv only transitively — several research scripts import it,
but it is not a ``src`` dependency, so importing it unconditionally here would risk an ImportError
in a minimal production install). Every sibling provider in this package already depends on httpx
transitively through its SDK (openai/groq are httpx-based); this is the first to call it directly.

Reuses ``AI_PROVIDER_REQUEST_TIMEOUT_SECONDS`` (``src/shared/constants/ai_provider_http.py``) for
BOTH the reachability probe and the chat call — the same deadline Groq and OpenRouter were fixed
to use in commit c2e25c565 (a stalled read hangs forever without one), not a new number invented
for this provider.

CLONE CHECK (clone_body_guard, ``apps/api/src/infrastructure/ai``, min_similarity 0.85), read
before writing this: five clusters already live here — ``explain_signal`` at 1.00 across claude/
gemini/groq/together, ``_classify_sync`` at 1.00 and ``_call_api`` at 0.94 across openrouter/
together, and ``_init_client`` at 1.00 plus ``_call_vision_api`` at 0.89 between
``ai_provider_claude.py`` and ``claude_client.py``. This provider's four matching-named methods
are NOT new copies of those clusters: the task explicitly requires mirroring the existing
provider INTERFACE (``is_configured`` / ``get_provider_name`` / ``explain_signal`` /
``_classify_sync`` / ``_call_api`` / ``_init_client``) so the fallback chain machinery in
``providers.py`` keeps working, but every body here differs materially from every clustered
sibling — no API key, no vendor SDK object, a raw ``httpx`` call against a locally-hosted REST
endpoint with Ollama's own request/response shape (``options.num_predict`` instead of
``max_tokens``, ``message.content`` instead of ``choices[0].message.content``). Structural
similarity in the surrounding scaffolding (async delegates to a sync call via
``asyncio.to_thread``, catches and re-raises as ``AIProviderUpstreamError``) is the shape the
existing ``AIProvider`` ABC asks every subclass to have, not a duplicated algorithm.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from src.infrastructure.ai.ai_provider_base import (
    DEFAULT_CLASSIFY_MAX_TOKENS,
    DEFAULT_LANGUAGE,
    SYSTEM_PROMPT,
    AIProvider,
    AIProviderUpstreamError,
    get_language_name,
)
from src.infrastructure.ai.ai_provider_ollama_constants import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OLLAMA_BASE_URL_ENV_VAR,
)
from src.infrastructure.config.settings import settings
from src.shared.constants.ai_provider_http import AI_PROVIDER_REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class OllamaAIProvider(AIProvider):
    """Local Ollama provider. No API key; "configured" means the local server answered."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        """Resolve the server URL, probe it once, and cache the reachability result.

        Args:
            base_url: Override for the server URL. If None, reads ``OLLAMA_BASE_URL`` then
                falls back to :data:`DEFAULT_OLLAMA_BASE_URL`.
            model: Default model id. If None, falls back to :data:`DEFAULT_OLLAMA_MODEL`.
        """
        resolved = base_url or os.environ.get(OLLAMA_BASE_URL_ENV_VAR) or DEFAULT_OLLAMA_BASE_URL
        self._base_url = resolved.rstrip("/")
        self._model = model or DEFAULT_OLLAMA_MODEL
        self._reachable = False
        self._init_client()

    def _init_client(self) -> None:
        """Probe the local server once. There is no SDK client to build — the probe result IS the state."""
        try:
            response = httpx.get(
                f"{self._base_url}/api/version",
                timeout=AI_PROVIDER_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            self._reachable = True
            logger.info("OllamaAIProvider initialized against %s (model=%s)", self._base_url, self._model)
        except Exception as e:
            logger.warning("Ollama server not reachable at %s: %s", self._base_url, e)
            self._reachable = False

    def is_configured(self) -> bool:
        """True when the local server answered the reachability probe."""
        return self._reachable

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "ollama"

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Generate explanation using the local Ollama model in the specified language."""
        if not self.is_configured():
            return self._format_response(
                f"AI explanation unavailable. Ollama server not reachable at {self._base_url}.",
                language,
            )

        language_name = get_language_name(language)
        user_prompt = (
            "Based on the following data, explain why this "
            f"trading signal was generated:\n\n{context}\n\n"
            f"IMPORTANT: Respond in {language_name}. "
            f"Use natural, fluent {language_name}."
        )
        try:
            response = await asyncio.to_thread(
                self._call_api,
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=max_tokens,
                model=model,
                temperature=temperature,
            )
            return self._format_response(response or "No explanation generated.", language)
        except Exception as e:
            logger.exception("Ollama API error: %s", e)
            raise AIProviderUpstreamError(self.get_provider_name()) from e

    def _call_api(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None,
        model: str | None,
        temperature: float | None,
    ) -> str:
        """POST one chat turn to the local server and return the assistant's text."""
        options: dict[str, Any] = {
            "temperature": temperature if temperature is not None else settings.ai_temperature,
        }
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": options,
        }

        response = httpx.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=AI_PROVIDER_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as e:
            # A local server returning a non-JSON body is a broken upstream, not a parse bug —
            # surface it the same way "no client" does for the keyed providers, instead of
            # letting a raw JSONDecodeError bubble out of a call site that expects text.
            raise AIProviderUpstreamError(self.get_provider_name()) from e

        message = data.get("message") if isinstance(data, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        return content if isinstance(content, str) else ""

    def _classify_sync(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None,
        model: str | None,
        temperature: float | None,
    ) -> str:
        """Lean classification via the local Ollama server (same chat endpoint as explain)."""
        if not self.is_configured():
            raise AIProviderUpstreamError(self.get_provider_name())
        return self._call_api(
            system=system,
            user=user,
            max_tokens=max_tokens if max_tokens is not None else DEFAULT_CLASSIFY_MAX_TOKENS,
            model=model,
            temperature=temperature,
        )
