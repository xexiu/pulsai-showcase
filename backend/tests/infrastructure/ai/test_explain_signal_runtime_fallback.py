"""Runtime explain_signal failover when upstream LLM calls fail."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.ai import ai_runtime_fallback as runtime_fallback
from src.infrastructure.ai.ai_provider_base import AIProviderUpstreamError


@pytest.mark.asyncio
async def test_uses_next_provider_when_first_raises_upstream_error() -> None:
    from src.infrastructure.ai import providers as providers_mod

    first = MagicMock()
    first.is_configured.return_value = True
    first.get_provider_name.return_value = "first"
    first.explain_signal = AsyncMock(side_effect=AIProviderUpstreamError("first"))

    second = MagicMock()
    second.is_configured.return_value = True
    second.get_provider_name.return_value = "second"
    second.explain_signal = AsyncMock(return_value="from second")

    factories = {
        "first": lambda: first,
        "second": lambda: second,
    }

    with (
        patch.object(runtime_fallback, "_PROVIDER_FACTORIES", factories),
        patch.object(
            runtime_fallback,
            "_explain_runtime_provider_names",
            return_value=("first", "second"),
        ),
    ):
        text, used = await providers_mod.explain_signal_with_runtime_fallback(
            None,
            "ctx",
            "en",
        )

    assert text == "from second"
    assert used == "second"


@pytest.mark.asyncio
async def test_skips_unconfigured_providers_in_chain() -> None:
    from src.infrastructure.ai import providers as providers_mod

    skip = MagicMock()
    skip.is_configured.return_value = False
    skip.get_provider_name.return_value = "skip"

    ok = MagicMock()
    ok.is_configured.return_value = True
    ok.get_provider_name.return_value = "ok"
    ok.explain_signal = AsyncMock(return_value="done")

    factories = {"skip": lambda: skip, "ok": lambda: ok}

    with (
        patch.object(runtime_fallback, "_PROVIDER_FACTORIES", factories),
        patch.object(
            runtime_fallback,
            "_explain_runtime_provider_names",
            return_value=("skip", "ok"),
        ),
    ):
        text, used = await providers_mod.explain_signal_with_runtime_fallback(
            None,
            "ctx",
            "en",
        )

    assert text == "done"
    assert used == "ok"
    skip.explain_signal.assert_not_called()
