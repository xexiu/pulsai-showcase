"""Outbound HTTP deadlines for the LLM providers. One number, one home.

IMPORTERS / CALLERS: ``src.infrastructure.ai.ai_provider_groq.GroqAIProvider._init_client`` and
  ``src.infrastructure.ai.ai_provider_openrouter.OpenRouterAIProvider._init_client``. Tests:
  ``tests/infrastructure/ai/test_ai_provider_modules.py::TestOutboundAiCallsAreTimeBounded``.
AFFECTED API: every endpoint that explains a signal or classifies text through an AI provider —
  they now fail in bounded time instead of holding a worker.
DATA SCHEMAS: none.
OWNER'S VERBATIM INSTRUCTION: "NO hardcoded values, strings, etc" and "Remember that all needs
  tested!!!".

REUSE-AUDIT: considered src/shared/constants/external_data.py, which already holds
DEFILLAMA_REQUEST_TIMEOUT_SECONDS. Not extending it: its own docstring scopes it to "the DefiLlama
stablecoin-supply display feature", and its other members are that provider's URL, name and cache
TTL. Putting an AI deadline there would make a feature-scoped module a general dumping ground —
the opposite of SoT. Considered src/shared/constants/ai_explain_config.py; not extending because
it holds admin RUNTIME-OVERRIDE KEYS (``ai_explain.param.temperature`` and friends), strings used
to look values up in a config store, not transport settings. Considered
src/infrastructure/ai/ai_provider_groq.py itself — a literal at the call site is the hardcoded
value the owner's standing rule forbids, and the OpenRouter sibling needs the same number, which
is precisely when a constant earns its module. The body-clone guard lists three clusters in this
package (env resolvers in _env_resolvers.py, concurrency resolvers in api_runtime.py, supported-
exchange getters in timeframes.py / trading.py); none is a timeout, and this module declares a
value rather than a function, so there is no body to duplicate.

WHY THIS FILE EXISTS — a five-hour silent hang, measured 2026-09-10.

The 4h ``llm_market_decision`` band run sat for **4h47m of wall clock on 6.3 seconds of CPU**,
frozen at ``125/421 decided``, its log untouched for 61 minutes, holding a single ESTABLISHED TCP
socket to Cloudflare (which fronts Groq). It neither finished nor failed.

The retry loop added the day before is what armed it. Before, a 429 raised ``RateLimitError`` and
killed the run LOUDLY. After, a 429 backs off and retries — right — but no individual call was
bounded, so one stalled read waits forever. ARCHITECTURE_PATTERNS.md section 5 names this exactly:
"a resilience pattern without observability is worse than none. It converts a loud failure into a
silent degradation." The retry was the resilience; the missing deadline was the observability.

The deadline lives in the PROVIDER rather than the research harness because production calls the
same client. A research script hanging costs a night; an API worker hanging costs the request pool.
"""

from __future__ import annotations

from typing import Final

#: Hard deadline for one LLM round trip, in seconds.
#:
#: 120s is chosen against the two failure modes, not picked round. A reasoning model answering a
#: market-state prompt takes single-digit seconds in the measured cache (1,245 recorded decisions),
#: so 120s is roughly an order of magnitude of headroom over the slow tail — it will not abort work
#: that would have succeeded. It is also far below the hour this hang burned, so a stall surfaces
#: while someone is still watching rather than overnight.
#:
#: Deliberately NOT the SDK default. The default is whatever the vendor last shipped; it is not a
#: decision anyone here made, and the incident above happened with it in force.
AI_PROVIDER_REQUEST_TIMEOUT_SECONDS: Final[float] = 120.0

__all__ = ["AI_PROVIDER_REQUEST_TIMEOUT_SECONDS"]
