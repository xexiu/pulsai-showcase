"""SoT constants for the FinBERT + LLM news-impact hybrid (Phase 2).

FinBERT scores financial-disclosure TONE and is blind to geopolitical / macro
impact — a Trump/Iran ceasefire reads NEUTRAL even though it is risk-on (bullish)
for crypto. A lean LLM impact pass classifies the macro headlines FinBERT misses;
these constants pin the prompt, the parse format, the token budget, and the
per-cycle call cap in ONE place (CODING_STANDARDS §12 — no magic numbers/strings).

WHY a lean prompt (not the signal-explain ``SYSTEM_PROMPT``)? That prompt is
~1500 tokens and frames the call as a trading-signal explanation. On Groq's free
tier (~6k TPM) it allows ~3.5 headlines/min; this one-line-in / one-line-out
prompt is ~180 tokens/call -> ~33/min (about 9x). Validated by
``src/research/finbert_vs_llm_news_impact_poc.py``.
"""

from typing import Final

# Lean classification system prompt. ONE line in, ONE line out — see module docstring.
NEWS_IMPACT_SYSTEM_PROMPT: Final[str] = (
    "You are a crypto macro analyst. Judge the SHORT-TERM (next few hours) directional "
    "impact of a NEWS HEADLINE on Bitcoin / crypto market prices. Consider geopolitics "
    "and macro risk-on/off, not just the literal tone. "
    "Answer on ONE line, EXACTLY this format and nothing else:\n"
    "VERDICT=<BULLISH|BEARISH|NEUTRAL> | CONF=<0.00-1.00>"
)

# Structural size budget for the lean prompt above (char proxy, ~4 chars/token). The
# heavy signal-explain SYSTEM_PROMPT is ~1500 tok (~6000 chars); the lean prompt must
# stay far below it so classification stays TPM-cheap on the free tier. ~800 chars
# (~200 tok) leaves headroom for legitimate edits while catching silent bloat. Enforced
# by tests/unit/architecture/test_ai_provider_isp_classification_routing.py.
NEWS_IMPACT_SYSTEM_PROMPT_MAX_CHARS: Final[int] = 800

# User-message template; the headline is the only variable input.
NEWS_IMPACT_USER_TEMPLATE: Final[str] = 'Headline: "{headline}"'

# Response cap — the verdict line is ~12 tokens; keep tight for TPM + cost.
NEWS_IMPACT_MAX_TOKENS: Final[int] = 24

# Deterministic classification (not creative writing).
NEWS_IMPACT_TEMPERATURE: Final[float] = 0.0

# A verdict below this confidence is treated as NEUTRAL (no actionable signal).
# Keeps a hedging "BULLISH conf=0.3" from moving the card.
NEWS_IMPACT_MIN_CONFIDENCE: Final[float] = 0.55

# Blend policy (conviction-weighted FinBERT + LLM). A macro-event verdict is worth
# ~3 crypto-native directional headlines (higher-impact AND exactly FinBERT's blind
# spot); the FinBERT side is capped so a sea of mildly-directional tone headlines
# cannot swamp a decisive macro verdict.
NEWS_IMPACT_FINBERT_WEIGHT_CAP: Final[float] = 8.0
NEWS_IMPACT_LLM_PER_VERDICT_WEIGHT: Final[float] = 3.0

# When the FRESHEST macro headline is directional (lead verdict), DeepSeek prevails over
# FinBERT's stale tone batch — cap FinBERT weight and boost the lead verdict so a single
# breaking macro line (e.g. Fed Sintra) can flip the card within one refresh cycle.
NEWS_IMPACT_FINBERT_WEIGHT_CAP_ON_LEAD: Final[float] = 2.0
NEWS_IMPACT_LEAD_VERDICT_WEIGHT: Final[float] = 8.0

# FinBERT vs LLM are in conflict when both are directional with OPPOSITE signs and
# each magnitude clears this deadband. Surfaced to the card so an averaged-away
# disagreement (e.g. bullish crypto tone vs a bearish Fed-hike verdict) stays visible.
NEWS_IMPACT_CONFLICT_DEADBAND: Final[float] = 0.1

# FinBERT tone centring (NEWS-3, 2026-09-11). FinBERT reads financial headlines as negative-toned: its
# effective value was negative on 89.5% of 9,709 prod snapshots (median -0.2305), which turned the LLM's
# 2.84:1 bearish lean into 9.8:1 at the 0.6 alert gate. The blend centres FinBERT on a CAUSAL trailing
# median of its own persisted effective value (snapshot extras ``finbert_effective_value``).
# Window MEASURED on the prod corpus 2026-08-06..09-11, every snapshot replayed through the blend, the
# alert gate and the 6h dedup: 3-, 7- and 14-day windows all cut the alert skew from 3.77:1 to ~1.6:1 at
# +5% alert volume, matching the lookahead global median. 7 days spans a whole weekly news cycle, and the
# weekly median drifted between -0.34 and -0.15, so a fixed constant would go stale. The minimum sample
# (one day of refreshes) is derived from the refresh cadence in the worker.
NEWS_IMPACT_FINBERT_BASELINE_WINDOW_DAYS: Final[int] = 7

# TPM safety: hard cap on LLM calls per refresh cycle. Macro-routed headlines
# beyond this are dropped (caller keeps the freshest and logs the drop — never a
# silent cap). At the 5-min cadence with per-headline caching, steady-state load
# is only the genuinely NEW macro headlines, so this is a spike guard.
# MEASURED 2026-08-25 localhost (7 cycles with n_macro_* telemetry): mean_total=36.1,
# max_total=38, drop_cycles=100%, mean_dropped=16.1 at the old cap of 20 — chronic
# starvation, not a rare spike. Raised to 40 (covers max observed + small headroom).
# Re-check via scripts/measure_news_impact_macro_cap.py + snapshot extras.
NEWS_IMPACT_MAX_HEADLINES_PER_CYCLE: Final[int] = 40

# Per-headline verdict cache TTL (seconds). A headline's text is immutable, so its
# impact verdict is too — caching by content hash means we pay the LLM once per
# unique headline, not once per 5-min cycle it lingers in the feed. 6h comfortably
# covers a headline's feed lifetime while bounding how long a verdict can go stale
# if the same exact text is re-contextualized by a breaking event.
# Directional verdicts can go stale when context shifts (same headline text, new macro read).
NEWS_IMPACT_CACHE_TTL_SECONDS: Final[int] = 21_600
NEWS_IMPACT_CACHE_TTL_DIRECTIONAL_SECONDS: Final[int] = 3_600

# Macro calendar → DeepSeek synthetic headlines (NOT FinBERT, NOT HTML scrapers).
# Reuses MacroSnapshot upcoming_events / recent_surprises (FRED schedule + TE surprises).
# Investing/BabyPips/Finviz/ForexFactory pages are HTML tools — never rss_url targets.
NEWS_IMPACT_CALENDAR_HORIZON_HOURS: Final[float] = 72.0
NEWS_IMPACT_CALENDAR_SOURCE: Final[str] = "macro_calendar"
