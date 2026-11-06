"""
Mock AI Provider.

Zero-cost provider for development and testing.

Extracted from providers.py for modularity.
"""

import asyncio
import logging
import random
from itertools import pairwise
from typing import Final

from src.domain.enums import SignalAction
from src.infrastructure.ai.ai_provider_base import (
    DEFAULT_LANGUAGE,
    VisionAIProvider,
)
from src.shared.chart_pattern_reference_stats import (
    build_mock_chart_analysis_response,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Mock Responses (for development/testing)
# =============================================================================

# Section headers (from rag_explain_signal_sections.py) that the mock provider
# surfaces in its response body. Mock templates are pre-written and do not
# reference these blocks; without this allowlist the user-visible modal in
# mock mode has no visual parity with what a real LLM would write from the
# same RAG context. Order is preserved in the rendered body.
MOCK_BODY_AUGMENT_SECTION_HEADERS: tuple[str, ...] = (
    "## Technical levels",
    "## Signal triggers",
    "## Position sizing",
)

# Conclusion-line formatting tunables. Pulled out as named constants per
# CODING_STANDARDS §12 (no magic numbers) so the multi-target ladder length
# and the multi vs single threshold can be adjusted in one place.
MULTI_TARGET_MIN_LEVELS: Final[int] = 2
MULTI_TARGET_MAX_LEVELS: Final[int] = 3

# Markers the mock scans for when building the multi-target Conclusion ladder.
# Order = render order in the rendered RAG ``## Technical levels`` block so the
# nearest (5-bar dist_to_*) wins T1. SoT for what counts as a "level" the mock
# is willing to cite; the prompt rule for the real LLM mirrors the same idea.
_BUY_LADDER_MARKERS: Final[tuple[str, ...]] = (
    "Nearest resistance",
    "Keltner upper",
    "CP resistance",
    "CP target",
)
_SELL_LADDER_MARKERS: Final[tuple[str, ...]] = (
    "Nearest support",
    "Keltner lower",
    "CP support",
    "CP stop-loss",
)

MOCK_EXPLANATIONS = {
    SignalAction.BUY.value: [
        """The model generated a **BUY** signal based on a confluence of bullish technical indicators.

The RSI is currently in oversold territory (below 30), suggesting potential upward price correction. Additionally, the MACD has crossed above the signal line, indicating building bullish momentum. The price is also approaching a key support level identified by the Bollinger Bands.

Given the {confidence}% confidence level, the model sees moderate probability of upward movement, though as with all predictions, this comes with uncertainty.""",
        """A **BUY** signal was triggered due to several technical factors aligning.

The Stochastic oscillator shows the asset is oversold with a bullish crossover forming. Volume analysis indicates accumulation, with buying volume exceeding selling pressure over recent candles. The EMA-20 is also starting to curve upward, suggesting trend reversal potential.

The model's {confidence}% confidence reflects the strength of these combined signals, though market conditions can change rapidly.""",
    ],
    SignalAction.SELL.value: [
        """The model generated a **SELL** signal based on bearish technical conditions.

RSI has entered overbought territory (above 70), often a precursor to price pullbacks. The MACD histogram is showing declining momentum, and price has touched the upper Bollinger Band, historically a resistance zone for this asset.

With {confidence}% confidence, the model suggests downward pressure is likely, though external factors like news events could override technical signals.""",
        """A **SELL** signal was identified based on multiple bearish indicators.

The asset is showing signs of exhaustion near key resistance levels. Volume on recent up-candles has been declining (bearish divergence), and the ADX indicates the current uptrend is losing strength. The model also detected a potential head-and-shoulders pattern forming.

The {confidence}% confidence indicates moderate certainty in this assessment.""",
    ],
    SignalAction.HOLD.value: [
        """The model generated a **HOLD** signal due to mixed or neutral technical conditions.

Current indicators are not showing clear directional bias. RSI is in neutral territory (40-60 range), the MACD is flat near the zero line, and price is consolidating within the middle Bollinger Bands. This typically indicates market indecision.

With {confidence}% confidence, the model suggests waiting for clearer signals before taking action. Consolidation periods often precede significant moves in either direction.""",
        """A **HOLD** signal was generated because the technical picture is inconclusive.

The market is currently range-bound with no clear trend. Volume has been below average, suggesting lack of conviction from either bulls or bears. Key moving averages (EMA-20, EMA-50) are flattening out, which typically indicates a period of consolidation.

The {confidence}% confidence reflects this uncertainty. It may be prudent to wait for a breakout confirmation before entering new positions.""",
    ],
}


class MockAIProvider(VisionAIProvider):
    """
    Mock AI provider for development and testing.

    WHY mock provider?
    - Zero cost during development
    - Instant responses (no API latency)
    - Works offline
    - Useful for UI testing
    """

    # SoT for the mock provider's identifier. Callers (endpoints, tests, the
    # `is_mock` flag computation) import this instead of hardcoding the string
    # so the name stays in one place. CODING_STANDARDS §12.
    PROVIDER_NAME: Final[str] = "mock"

    def __init__(self) -> None:
        """Initialize mock provider."""
        logger.info("MockAIProvider initialized - using template responses")

    def is_configured(self) -> bool:
        """Mock is always configured."""
        return True

    def get_provider_name(self) -> str:
        """Return provider name."""
        return self.PROVIDER_NAME

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
        Generate mock explanation based on signal action.

        Parses the context to determine action and confidence,
        then returns a realistic template response.

        Note: Mock responses are always in English (templates are hardcoded).
        Real providers (Groq, Claude) will respond in the requested language.
        """
        # Simulate API latency (100-500ms) - using random is fine for mock, not cryptographic
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Parse action and confidence from context
        action = SignalAction.HOLD
        confidence = 50

        if "Action: BUY" in context:
            action = SignalAction.BUY
        elif "Action: SELL" in context:
            action = SignalAction.SELL
        elif "Action: HOLD" in context:
            action = SignalAction.HOLD

        # Extract confidence
        if "Confidence:" in context:
            try:
                conf_part = context.split("Confidence:")[1].split("%", maxsplit=1)[0]
                confidence = int(conf_part.strip())
            except IndexError, ValueError:
                pass

        # Select random template and format - using random is fine for mock variation
        templates = MOCK_EXPLANATIONS.get(action.value, MOCK_EXPLANATIONS[SignalAction.HOLD.value])
        template = random.choice(templates)
        body = template.format(confidence=confidence)

        # Mock must satisfy the same Conclusion contract real providers do
        # so the BE parser produces a populated `conclusion` field downstream.
        # Per-action target via the SoT computation: BUY uses the nearest
        # resistance, SELL uses the nearest support, HOLD uses the snapshot
        # price. See ``infrastructure/ai/explain_target_price.py``.
        # Surface RAG sections the templates do not mention (technical levels,
        # position sizing) so dev mode has visual parity with a real LLM.
        # Appended BEFORE the Conclusion line so the parser keeps treating
        # Conclusion as the final body line.
        augmented_body = self._augment_body_with_rag_sections(body, context)
        conclusion_line = self._render_conclusion_line(context, action, confidence)
        response = f"{augmented_body}\n{conclusion_line}"

        logger.info("MockAIProvider: Generated %s explanation (lang=%s)", action, language)
        return self._format_response(response, language)

    def _classify_sync(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None,
        model: str | None,
        temperature: float | None,
    ) -> str:
        """Return a parseable NEUTRAL verdict.

        Mock has no real classifier, so it emits no directional signal — the
        news-impact blend then reduces to FinBERT (Phase 1) in dev / CI / no-key
        environments instead of fabricating a bullish/bearish call.
        """
        return "VERDICT=NEUTRAL | CONF=0.00"

    @classmethod
    def _render_conclusion_line(cls, context: str, action: SignalAction, confidence: int) -> str:
        """Render the final Conclusion line — single- or multi-target per action.

        Thin orchestrator: HOLD always single; BUY/SELL try the multi-target
        ladder first, fall back to single. Collection and formatting are
        separate helpers so each is independently testable (SRP).
        """
        if action == SignalAction.HOLD:
            return cls._format_single_target_conclusion(context, action, confidence)
        ladder = cls._collect_ladder(context, action)
        if len(ladder) >= MULTI_TARGET_MIN_LEVELS:
            return cls._format_multi_target_conclusion(action, confidence, ladder)
        return cls._format_single_target_conclusion(context, action, confidence)

    @classmethod
    def _collect_ladder(cls, context: str, action: SignalAction) -> list[str]:
        """Build the resistance/support price ladder for ``action`` in document order.

        Deduplicates so close 5-bar / 20-bar / Keltner / CP levels collapse to
        one entry (LLM/mock prefer breadth across detector types). The marker
        order is SoT: ``_BUY_LADDER_MARKERS`` / ``_SELL_LADDER_MARKERS``.
        """
        markers = _BUY_LADDER_MARKERS if action == SignalAction.BUY else _SELL_LADDER_MARKERS
        ladder: list[str] = []
        for marker in markers:
            for price in cls._collect_prices(context, marker):
                if price not in ladder:
                    ladder.append(price)
        return ladder

    @staticmethod
    def _format_multi_target_conclusion(action: SignalAction, confidence: int, ladder: list[str]) -> str:
        """Stringify a ``targets $T1 / $T2 / $T3 est`` Conclusion line."""
        targets_str = " / ".join(f"${price}" for price in ladder[:MULTI_TARGET_MAX_LEVELS])
        return f"Conclusion: {action.value} {confidence}% targets {targets_str} est"

    @classmethod
    def _format_single_target_conclusion(cls, context: str, action: SignalAction, confidence: int) -> str:
        """Stringify a ``target $X est`` Conclusion line for HOLD or single-level BUY/SELL."""
        target_price = cls._extract_target_for_action(context, action)
        return f"Conclusion: {action.value} {confidence}% target ${target_price} est"

    @classmethod
    def _collect_prices(cls, context: str, marker: str) -> list[str]:
        """Return ALL prices found on lines containing ``marker``, in document order."""
        prices: list[str] = []
        for raw_line in context.splitlines():
            if marker not in raw_line:
                continue
            price = cls._extract_first_price_from_line(raw_line)
            if price is not None:
                prices.append(price)
        return prices

    @staticmethod
    def _extract_first_price_from_line(raw_line: str) -> str | None:
        """Pull the first ``$<number>`` token from a single rendered line."""
        dollar = raw_line.find("$")
        if dollar < 0:
            return None
        tail = raw_line[dollar + 1 :].lstrip()
        buf: list[str] = []
        for char in tail:
            if char.isdigit() or char in (",", "."):
                buf.append(char)
            else:
                break
        if not buf:
            return None
        return "".join(buf).replace(",", "")

    @staticmethod
    def _extract_target_for_action(context: str, action: SignalAction) -> str:
        """Pick the Conclusion target price per action from the rendered RAG context.

        BUY  → "Nearest resistance ...: ~$X" line from the technical_levels section.
        SELL → "Nearest support    ...: ~$X" line from the technical_levels section.
        HOLD → snapshot price line.

        Falls through to the legacy "Price at signal time" header line if the
        technical_levels section was disabled or its data was missing — keeps
        the mock useful in degraded scenarios.
        """
        if action == SignalAction.BUY:
            level = MockAIProvider._find_first_price(context, "Nearest resistance")
            if level is not None:
                return level
        elif action == SignalAction.SELL:
            level = MockAIProvider._find_first_price(context, "Nearest support")
            if level is not None:
                return level
        # HOLD (or no level data for BUY/SELL): prefer the snapshot price
        # rendered by the technical_levels section, then the legacy
        # "Price at signal time" header marker, then the constant fallback.
        snapshot = MockAIProvider._find_first_price(context, "Snapshot price")
        if snapshot is not None:
            return snapshot
        legacy = MockAIProvider._find_first_price(context, "Price at signal time")
        if legacy is not None:
            return legacy
        # Non-zero placeholder so the parser produces a valid conclusion in
        # tests / smoke runs where the context lacks any price line.
        return "100"

    @classmethod
    def _find_first_price(cls, context: str, marker: str) -> str | None:
        """Return the first ``$<number>`` token on the first line containing ``marker``.

        Marker-scoped wrapper around :meth:`_extract_first_price_from_line` so
        the dollar/comma parsing rules live in ONE place (CODING_STANDARDS §2).
        Returns ``None`` when the marker is absent OR no parseable price
        follows it.
        """
        for raw_line in context.splitlines():
            if marker not in raw_line:
                continue
            price = cls._extract_first_price_from_line(raw_line)
            if price is not None:
                return price
        return None

    @staticmethod
    def _extract_sections(context: str, header_prefixes: tuple[str, ...]) -> dict[str, str]:
        """Single-pass extraction of every ``header_prefix`` in ``context``.

        Walks the context lines ONCE, building a header→block dict. Replaces
        the previous per-header re-scan (O(N·H) → O(N)) called out by the
        architecture audit. Returns blocks keyed by the prefix that matched —
        callers pick the order they want to render.
        """
        lines = context.splitlines()
        # First pass: locate every ``## ``-prefixed line and the prefix it matches.
        boundaries: list[tuple[int, str | None]] = []
        for idx, line in enumerate(lines):
            if not line.startswith("## "):
                continue
            match = next((p for p in header_prefixes if line.startswith(p)), None)
            boundaries.append((idx, match))
        if not boundaries:
            return {}
        # Append sentinel so the last block's end is computed uniformly.
        boundaries.append((len(lines), None))
        result: dict[str, str] = {}
        for (start, matched_prefix), (end, _) in pairwise(boundaries):
            if matched_prefix is None or matched_prefix in result:
                continue
            block = "\n".join(lines[start:end]).strip("\n")
            if block:
                result[matched_prefix] = block
        return result

    @classmethod
    def _augment_body_with_rag_sections(cls, body: str, context: str) -> str:
        """Append the whitelisted RAG sections found in ``context`` to ``body``.

        Sections appear in the order declared by
        ``MOCK_BODY_AUGMENT_SECTION_HEADERS``. When the context has none of
        them, ``body`` is returned unchanged.
        """
        found = cls._extract_sections(context, MOCK_BODY_AUGMENT_SECTION_HEADERS)
        extras = [found[header] for header in MOCK_BODY_AUGMENT_SECTION_HEADERS if header in found]
        if not extras:
            return body
        return body + "\n\n" + "\n\n".join(extras)

    async def analyze_chart(
        self,
        image_base64: str,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        model_override: str | None = None,
    ) -> str:
        """Generate mock chart analysis."""
        # The mock returns canned text; the argument exists because the vision contract has it.
        _ = image_base64
        await asyncio.sleep(random.uniform(0.2, 0.5))

        return self._format_response(build_mock_chart_analysis_response(), language)
