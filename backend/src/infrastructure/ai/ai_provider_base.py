"""
AI Provider Base Module.

Contains abstract base class and shared constants for all AI providers.

Extracted from providers.py for modularity.

Language Configuration:
- DEFAULT_LANGUAGE: Loaded from settings.ai_default_language
- SUPPORTED_LANGUAGES: Built from settings.ai_supported_languages_list
- LANGUAGE_NAMES: Factual mapping of ISO codes to full names (static)
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from src.infrastructure.config.settings import settings
from src.shared.constants.ai_explain_conclusion import EXPLAIN_MAX_LINES

logger = logging.getLogger(__name__)

# Fallback response cap for lean classification calls when the caller passes none.
# Tight by design — classification answers are a single short line. Providers use
# this only when ``max_tokens`` is None so they stay decoupled from any one caller's
# token budget (the news-impact caller passes NEWS_IMPACT_MAX_TOKENS).
DEFAULT_CLASSIFY_MAX_TOKENS = 64

# Upstream HTTP statuses treated as "expected" (WARNING, no traceback): transient outages
# (429/500/502/503/529) plus 402 — a handled billing/quota stop. 402 is not transient, but the
# failover chain degrades to the next provider / FinBERT, so it recurs every refresh cycle once a
# key runs dry and must not flood ERROR tracebacks (it is operational, not a code bug).
_EXPECTED_UPSTREAM_STATUS = frozenset({402, 429, 500, 502, 503, 529})

# =============================================================================
# Language Configuration
# =============================================================================

# Factual mapping of ISO 639-1 codes to full language names.
# WHY full names? LLMs respond better to "Respond in Spanish" than "Respond in es"
# This mapping is static (facts don't change), but which languages are ENABLED
# is configurable via settings.ai_supported_languages
LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "en": "English",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
}

# Load default language from settings (configurable per deployment)
# WHY configurable? Different deployments target different markets
# (LATAM = Spanish, US = English, Europe = varies)
DEFAULT_LANGUAGE = settings.ai_default_language

# Build SUPPORTED_LANGUAGES from settings-configured codes
# Only includes languages that are both in LANGUAGE_NAMES AND enabled in settings
SUPPORTED_LANGUAGES: dict[str, str] = {code: LANGUAGE_NAMES[code] for code in settings.ai_supported_languages_list if code in LANGUAGE_NAMES}


def get_language_name(lang_code: str) -> str:
    """
    Get full language name from ISO code.

    WHY full names?
    - LLMs respond better to "Respond in Spanish" than "Respond in es"
    - More natural instruction format
    - Reduces ambiguity

    Args:
        lang_code: ISO 639-1 language code (e.g., "es", "en")

    Returns:
        Full language name, defaults to Spanish if not found
    """
    return SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])


# Localized disclaimers (shown at end of AI responses)
DISCLAIMERS: dict[str, str] = {
    "es": (
        "\n\n---\n"
        "*Aviso: Este es un análisis generado por IA solo con fines informativos. "
        "No es asesoramiento financiero. Siempre haga su propia investigación antes de tomar decisiones de trading.*"
    ),
    "en": (
        "\n\n---\n"
        "*Disclaimer: This is AI-generated analysis for informational purposes only. "
        "It is not financial advice. Always do your own research before making trading decisions.*"
    ),
    "fr": (
        "\n\n---\n"
        "*Avertissement: Cette analyse est générée par IA à titre informatif uniquement. "
        "Ce n'est pas un conseil financier. Faites toujours vos propres recherches avant de prendre des décisions de trading.*"
    ),
    "it": (
        "\n\n---\n"
        "*Avviso: Questa è un'analisi generata dall'IA solo a scopo informativo. "
        "Non è una consulenza finanziaria. Fai sempre le tue ricerche prima di prendere decisioni di trading.*"
    ),
    "pt": (
        "\n\n---\n"
        "*Aviso: Esta é uma análise gerada por IA apenas para fins informativos. "
        "Não é aconselhamento financeiro. Sempre faça sua própria pesquisa antes de tomar decisões de trading.*"
    ),
    "de": (
        "\n\n---\n"
        "*Haftungsausschluss: Dies ist eine KI-generierte Analyse nur zu Informationszwecken. "
        "Es handelt sich nicht um Finanzberatung. Recherchieren Sie immer selbst, bevor Sie Handelsentscheidungen treffen.*"
    ),
}

# Fallback for backwards compatibility
DISCLAIMER = DISCLAIMERS["en"]


SYSTEM_PROMPT = f"""You are a trading assistant for PulsAI, an AI-powered cryptocurrency trading platform.

Your job is to explain a trading signal AND each enabled feature section provided in the user
message (ML headline, weighted consensus, classic TA rules, news sentiment, on-chain metrics,
feature importance, sizing hint), then produce ONE structured Conclusion line as the model's
summary of the inputs.

RULES:
1. Be factual and data-driven — cite values from the sections present.
2. Cover the enabled sections briefly: one short bullet or sentence per section.
3. Mention uncertainty when components disagree or confidence is low. In particular,
   if the weighted-consensus section shows a dissenting action with >= 10% of the
   weight (e.g. "16% SELL" alongside an 84% HOLD headline), CALL IT OUT explicitly
   — this is the signal's known disagreement and the user must see it.
4. Frame the Conclusion as the MODEL'S SUMMARY of the signal + features, NOT personal advice.
   The user-facing response carries an explicit "not financial advice" disclaimer.
5. MAXIMUM {EXPLAIN_MAX_LINES} LINES TOTAL, including the Conclusion line. Be concise.
6. The LAST line MUST be exactly in one of these two formats (no extra text after):
   Single target:  Conclusion: <BUY|SELL|HOLD> <CONFIDENCE>% target $<PRICE> est
   Multi target:   Conclusion: <BUY|SELL> <CONFIDENCE>% targets $<T1> / $<T2> / $<T3> est
   - <CONFIDENCE> is an integer 0..100 reflecting agreement across enabled sections.
   - <PRICE> / <T1..T3> must be ACTION-ANCHORED via the "Technical levels" section when present:
     * BUY  → resistance levels ABOVE the snapshot price; nearest first.
              Single-target: cite the closest resistance.
              Multi-target: T1 = nearest resistance, T2/T3 = further resistance levels
              (e.g. dist_to_resistance_20, Keltner upper) when available.
     * SELL → support levels BELOW the snapshot price; nearest first.
              Same rule mirrored (T1 = nearest support, T2/T3 = further supports).
     * HOLD → ALWAYS the single-target form; cite the snapshot price.
     If the Technical levels section is absent, fall back to single-target with the snapshot price.
   - For BUY/SELL prefer the multi-target form when the Technical levels section provides
     2+ usable resistance/support levels; otherwise use single-target.
   - Always include the trailing "est" qualifier to mark prices as estimates.

TRADER NARRATIVE (when the matching section is present in the user message):
7. CP stop-loss → state it EXPLICITLY as the invalidation level for the trade idea
   (e.g. "Pattern invalidates below $X (CP stop-loss)"). One short line, no advice framing —
   it's the level cited by the pattern, not personal guidance.
8. CP target → reference it alongside the Conclusion targets so the user sees the geometric
   measured-move price as well as the nearest resistance/support.
9. Position sizing → restate the worked $ example in plain language
   (e.g. "Half-Kelly hint: 5.00% → ~$50 of a $1,000 reference capital").
   Do NOT invent your own capital figure — only use the one in the section.
10. Signal triggers (ST / RSI divergence / MACD divergence) → for each firing trigger,
    say one phrase whether it CONFIRMS or CONTRADICTS the headline action. Skip silent ones.
11. Tie it together: in 1-2 lines describe what these inputs mean as a coherent picture
    (entry vicinity → targets → invalidation → sizing). Stay descriptive, never imperative —
    "the data points to …" not "you should …".

FORBIDDEN:
- Direct personal advice ("you should buy/sell").
- Guarantees or claims about future price movements.
- Comparisons to other platforms.
- Inventing capital figures, account sizes, or PnL projections beyond the section's worked example.
- Any text after the Conclusion line.
"""


class AIProviderUpstreamError(RuntimeError):
    """Upstream LLM call failed (quota, outage, invalid key); caller may try another provider."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"AI upstream failure: {provider_name}")


# =============================================================================
# Abstract Base Class
# =============================================================================


class AIProvider(ABC):
    """
    Abstract base class for text-only AI providers.

    WHY abstract class?
    - Enforces consistent interface across providers
    - Allows easy swapping between providers
    - Enables mock testing without real API calls

    ISP: Text-only interface. For vision (chart analysis), see VisionAIProvider.
    """

    @property
    def name(self) -> str:
        """Provider name property for convenience."""
        return self.get_provider_name()

    @property
    def supports_vision(self) -> bool:
        """Whether this provider supports chart image analysis."""
        return False

    @abstractmethod
    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """
        Generate explanation for a trading signal.

        Args:
            context: RAG context with signal data and indicators
            language: ISO 639-1 language code for response
            temperature: per-call sampling temperature override (None → provider default)
            max_tokens: per-call response token cap override (None → provider default)
            model: per-call model id override (None → provider default)

        Returns:
            AI-generated explanation in the specified language
        """

    async def classify_text(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Lean text completion: caller-supplied system + user prompt, RAW response.

        Distinct from :meth:`explain_signal`, which injects the ~1500-token trading
        ``SYSTEM_PROMPT`` and appends a localized disclaimer. Those would 4x the token
        cost of a short classification (e.g. news-impact) call and blow free-tier TPM,
        so this path sends ONLY the supplied prompts and returns the model text verbatim.

        Concrete here (not abstract) so unknown subclasses / test doubles keep working;
        the default delegates to :meth:`_classify_sync`, whose base implementation marks
        the provider as not supporting classification by raising
        :class:`AIProviderUpstreamError` — the failover chain then skips to the next
        provider. Real providers override ``_classify_sync`` only (the async/threading/
        error-mapping boilerplate stays here, DRY).
        """
        try:
            return await asyncio.to_thread(
                self._classify_sync,
                system=system,
                user=user,
                max_tokens=max_tokens,
                model=model,
                temperature=temperature,
            )
        except AIProviderUpstreamError:
            raise
        except Exception as exc:
            if self._is_expected_upstream_error(exc):
                # Free-tier rate limit / transient outage: WARNING without a traceback
                # (these recur per cycle; the chain just skips to the next provider).
                logger.warning("classify_text rate-limited/unavailable for %s: %s", self.get_provider_name(), exc)
            else:
                logger.exception("classify_text failed for %s: %s", self.get_provider_name(), exc)
            raise AIProviderUpstreamError(self.get_provider_name()) from exc

    def _is_expected_upstream_error(self, exc: Exception) -> bool:
        """Whether ``exc`` is an expected upstream condition (rate limit / transient outage).

        Duck-typed so it works across every provider SDK without importing each one:
        matches a rate-limit / overloaded exception by class name, or a known transient
        HTTP status on the exception. Expected conditions log as WARNING (no traceback) —
        critical because Groq, the free-tier news-impact primary, is rate-limited as a
        matter of course and would otherwise spam ERROR tracebacks every refresh cycle.
        """
        status = getattr(exc, "status_code", None)
        if not isinstance(status, int):
            status = getattr(exc, "status", None)
        if isinstance(status, int) and status in _EXPECTED_UPSTREAM_STATUS:
            return True
        name = type(exc).__name__
        return any(marker in name for marker in ("RateLimit", "Overloaded", "ServiceUnavailable"))

    def _classify_sync(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None,
        model: str | None,
        temperature: float | None,
    ) -> str:
        """Synchronous lean classification call. Default: provider does not support it."""
        raise AIProviderUpstreamError(self.get_provider_name())

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name for display."""

    def _format_response(self, response: str, language: str = DEFAULT_LANGUAGE) -> str:
        """
        Add localized disclaimer to response.

        Args:
            response: AI-generated response text
            language: ISO 639-1 language code for disclaimer

        Returns:
            Response with localized disclaimer appended
        """
        disclaimer = DISCLAIMERS.get(language, DISCLAIMERS[DEFAULT_LANGUAGE])
        return response + disclaimer


class VisionAIProvider(AIProvider):
    """
    AI provider with vision (chart analysis) capabilities.

    WHY SEPARATE from AIProvider (ISP)?
    Not all providers support vision. Groq only does text — forcing it to
    implement analyze_chart was an ISP violation (dummy method, noqa: ARG002).
    Splitting lets text-only providers avoid an interface they cannot fulfill.
    """

    @property
    def supports_vision(self) -> bool:
        """Vision providers support chart analysis."""
        return True

    @abstractmethod
    async def analyze_chart(
        self,
        image_base64: str,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        model_override: str | None = None,
    ) -> str:
        """
        Analyze a chart image.

        Args:
            image_base64: Base64-encoded chart image
            context: Additional context (symbol, timeframe)
            language: ISO 639-1 language code for response
            model_override: Optional model ID override (OpenRouter only)

        Returns:
            AI-generated chart analysis in the specified language
        """
        # Named so the contract's own argument is not reported as dead code, and raising keeps the
        # method honest for mypy: a body with a statement in it owes a return, and "not
        # implemented here" is the truthful one. Every concrete vision provider overrides this.
        _ = image_base64
        raise NotImplementedError(self.get_provider_name())
