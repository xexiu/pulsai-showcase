"""The vision fallback chain may only contain providers that can actually do vision.

`analyze_chart_with_runtime_fallback` calls `client.analyze_chart(...)`, which is declared on
`VisionAIProvider` and NOT on `AIProvider` -- deliberate interface segregation, because several
providers are text-only. `providers.py` records the rule at the chain definition: "Groq is
text-only (no analyze_chart) -- never put it on a vision chain."

The factories are typed to the base class, and the loop deliberately does NOT isinstance-gate
(its own comment: gating breaks test doubles, since production classes already subclass). So the
call site casts to the narrower type -- and a cast is worth exactly as much as the invariant
behind it.

This is that invariant, checked instead of trusted: every name the chain can yield must resolve
to a `VisionAIProvider`. If someone adds a text-only provider to the chain, this fails here
rather than as an AttributeError inside a user's chart request.
"""

from __future__ import annotations

from src.infrastructure.ai.ai_provider_base import VisionAIProvider
from src.infrastructure.ai.ai_runtime_fallback import _ANALYZE_CHART_RUNTIME_CHAIN, _PROVIDER_FACTORIES


def test_every_name_on_the_vision_chain_is_a_known_provider() -> None:
    """A name with no factory would raise KeyError mid-request."""
    unknown = [name for name in _ANALYZE_CHART_RUNTIME_CHAIN if name not in _PROVIDER_FACTORIES]

    assert not unknown, f"vision chain names with no registered factory: {unknown}"


def test_every_provider_on_the_vision_chain_can_analyze_a_chart() -> None:
    """BEHAVIOUR: the cast at the call site cannot be wrong."""
    text_only: list[str] = []

    for name in _ANALYZE_CHART_RUNTIME_CHAIN:
        client = _PROVIDER_FACTORIES[name]()
        if not isinstance(client, VisionAIProvider):
            text_only.append(f"{name} -> {type(client).__name__}")

    assert not text_only, (
        "these are on the vision fallback chain but are not VisionAIProviders, so "
        "`analyze_chart` would raise AttributeError inside a user's request: " + ", ".join(text_only)
    )


def test_the_chain_is_not_empty() -> None:
    """Guard the guard: an empty chain would make both assertions above vacuous."""
    assert _ANALYZE_CHART_RUNTIME_CHAIN, "no vision providers configured — the checks above prove nothing"
