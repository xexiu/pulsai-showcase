"""Runtime analyze_chart failover when OpenRouter credits drain / vision upstream fails.

DISMISSAL-CHECK: not a hypothesis (shared infra tests) — mirrors
``test_explain_signal_runtime_fallback.py`` for the vision path.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.ai import ai_runtime_fallback as runtime_fallback
from src.infrastructure.ai.ai_provider_base import AIProviderUpstreamError


@pytest.mark.asyncio
async def test_analyze_chart_falls_to_gemini_when_openrouter_raises() -> None:
    from src.infrastructure.ai import providers as providers_mod

    openrouter = MagicMock()
    openrouter.is_configured.return_value = True
    openrouter.get_provider_name.return_value = "openrouter"
    openrouter.analyze_chart = AsyncMock(side_effect=AIProviderUpstreamError("openrouter"))

    gemini = MagicMock()
    gemini.is_configured.return_value = True
    gemini.get_provider_name.return_value = "gemini"
    gemini.analyze_chart = AsyncMock(return_value="from gemini native")

    factories = {
        "openrouter": lambda: openrouter,
        "gemini": lambda: gemini,
    }

    with (
        patch.object(runtime_fallback, "_PROVIDER_FACTORIES", factories),
        patch.object(
            runtime_fallback,
            "_analyze_chart_runtime_provider_names",
            return_value=("openrouter", "gemini"),
        ),
    ):
        text, used = await providers_mod.analyze_chart_with_runtime_fallback(
            None,
            image_base64="abc",
            context="ctx",
            language="en",
        )

    assert text == "from gemini native"
    assert used == "gemini"
    openrouter.analyze_chart.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_chart_skips_non_vision_configured_gap() -> None:
    from src.infrastructure.ai import providers as providers_mod

    skip = MagicMock()
    skip.is_configured.return_value = False

    ok = MagicMock()
    ok.is_configured.return_value = True
    ok.get_provider_name.return_value = "gemini"
    ok.analyze_chart = AsyncMock(return_value="ok")

    with (
        patch.object(
            runtime_fallback,
            "_PROVIDER_FACTORIES",
            {"openrouter": lambda: skip, "gemini": lambda: ok},
        ),
        patch.object(
            runtime_fallback,
            "_analyze_chart_runtime_provider_names",
            return_value=("openrouter", "gemini"),
        ),
    ):
        text, used = await providers_mod.analyze_chart_with_runtime_fallback(
            None,
            image_base64="x",
            context="c",
            language="en",
        )

    assert used == "gemini"
    assert text == "ok"
