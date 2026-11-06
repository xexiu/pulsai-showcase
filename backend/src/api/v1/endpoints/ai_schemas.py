"""Pydantic request and response models for the AI API endpoints.

`ConclusionAction` and `ExplainConclusion` are re-exported from the domain
layer (see `src.domain.models.explain_conclusion`). They live in domain
because both the API schema (this file) and the infrastructure parser
need them — moving them out of `src.api` keeps the infrastructure → api
import-linter contract satisfied.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.domain.models.explain_conclusion import ConclusionAction, ExplainConclusion

__all__ = [
    "AIStatusResponse",
    "APIResponse",
    "AnalyzeChartRequest",
    "AnalyzeChartResponse",
    "ConclusionAction",
    "ExplainConclusion",
    "ExplainSignalRequest",
    "ExplainSignalResponse",
    "ExplainSignalsRequest",
    "ExplainSignalsResponse",
    "MockModeRequest",
]


class ExplainSignalRequest(BaseModel):
    """Request to explain a trading signal.

    Section inclusion (news, on-chain, ML consensus, etc.) is no longer a
    per-call request flag — it is governed by the admin-controlled
    `AIExplainConfigService` (SoT) and the user's subscription tier. The FE
    should NOT send `include_news` or similar per-call toggles; what the
    explanation includes is a system policy, not a client choice.
    """

    signal_id: UUID = Field(..., description="UUID of the signal to explain")
    language: str = Field(
        default="es",
        description="ISO 639-1 language code for AI response (es, en, fr, it, pt, de)",
    )


class ExplainSignalResponse(BaseModel):
    """AI explanation response."""

    explanation: str = Field(..., description="AI-generated explanation (max 10 lines)")
    signal_id: str = Field(..., description="Signal that was explained")
    model_used: str | None = Field(
        default=None,
        description="AI model/provider used (admin/super_admin only; omitted for regular users).",
    )
    is_mock: bool = Field(default=False, description="Whether mock mode was used")
    llm_model: str | None = Field(
        default=None,
        description="Admin-configured model id when set (e.g. claude-3-5-sonnet).",
    )
    key_factors: list[str] | None = Field(default=None, description="Top explanation factors")
    conclusion: ExplainConclusion | None = Field(
        default=None,
        description="Structured verdict parsed from the final Conclusion line. Null if parsing failed.",
    )
    prompt_context: str | None = Field(
        default=None,
        description=(
            "Rendered RAG context fed to the LLM. Exposed so the FE can show it behind a"
            " 'Show prompt context' toggle for transparency/debugging. None when omitted."
        ),
    )


class ExplainSignalsRequest(BaseModel):
    """Request to explain a symbol's multi-timeframe confluence in ONE explanation.

    A trading confluence (several timeframes firing co-temporally) is a single
    decision the user acts on, so it gets one combined explanation rather than N
    fragmented ones. Section inclusion is governed by the admin config + tier (see
    ``ExplainSignalRequest``), not per-call flags.
    """

    symbol: str = Field(..., description="Trading pair (e.g. BTC/USDT) to explain the confluence for")
    timeframes: list[str] | None = Field(
        default=None,
        description="Timeframes to include; None = all alignment timeframes (latest signal per timeframe).",
    )
    language: str = Field(
        default="es",
        description="ISO 639-1 language code for AI response (es, en, fr, it, pt, de)",
    )

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        """Match the stored canonical form so 'btc/usdt' resolves the same rows as 'BTC/USDT'."""
        return value.strip().upper()


class ExplainSignalsResponse(BaseModel):
    """Combined multi-timeframe confluence explanation response."""

    explanation: str = Field(..., description="AI-generated combined explanation")
    symbol: str = Field(..., description="Symbol the confluence was explained for")
    timeframes: list[str] = Field(..., description="Timeframes included, shortest→longest")
    dominant_action: str = Field(..., description="BUY / SELL / HOLD / MIXED across the timeframes")
    is_conflicted: bool = Field(..., description="At least one BUY and one SELL leg (directional clash)")
    model_used: str | None = Field(default=None, description="AI provider used (admin/super_admin only).")
    is_mock: bool = Field(default=False, description="Whether mock mode was used")
    llm_model: str | None = Field(default=None, description="Admin-configured model id when set.")
    key_factors: list[str] | None = Field(default=None, description="Top explanation factors")
    conclusion: ExplainConclusion | None = Field(
        default=None,
        description="Structured verdict parsed from the final Conclusion line. Null if parsing failed.",
    )
    prompt_context: str | None = Field(
        default=None,
        description="Rendered RAG context (admin/super_admin only; None otherwise).",
    )


class AnalyzeChartRequest(BaseModel):
    """Request to analyze a chart image."""

    image_base64: str = Field(..., description="Base64-encoded chart image")
    symbol: str = Field(..., description="Trading pair symbol")
    timeframe: str = Field(default="1h", description="Chart timeframe")
    language: str = Field(
        default="es",
        description="ISO 639-1 language code for AI response (es, en, fr, it, pt, de)",
    )
    vision_model_override: str | None = Field(
        default=None,
        description="Optional OpenRouter vision model ID (e.g. google/gemma-3-12b-it:free)",
    )


class AnalyzeChartResponse(BaseModel):
    """Chart analysis response."""

    analysis: str = Field(..., description="AI-generated chart analysis")
    symbol: str
    timeframe: str
    model_used: str | None = Field(
        default=None,
        description="Vision provider slug (admin/super_admin only).",
    )
    is_mock: bool = Field(
        default=False,
        description="Whether mock mode served the analysis (admin/super_admin only).",
    )
    llm_model: str | None = Field(
        default=None,
        description="Vision model override id when set (admin/super_admin only).",
    )


class AIStatusResponse(BaseModel):
    """AI status response for admin."""

    mock_mode: bool = Field(description="Whether mock mode is active")
    current_provider: str = Field(description="Current active provider")
    providers: list[dict[str, Any]] = Field(description="Available providers")


class APIResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool = True
    data: dict[str, Any] | ExplainSignalResponse | ExplainSignalsResponse | AnalyzeChartResponse | AIStatusResponse


class MockModeRequest(BaseModel):
    """Request to toggle mock mode."""

    enabled: bool = Field(description="Enable or disable mock mode")
