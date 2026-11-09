"""Pin: Analyze Chart OpenRouter vision must be image-capable AND routable under account privacy.

MEASURED 2026-08-25:
- ``deepseek/deepseek-v4-flash-vision-exp`` is text+image in the catalogue but OpenRouter
  returns HTTP 404 (privacy/ZDR) on this account — unusable as the pin.
- ``google/gemini-3.5-flash-lite`` is text+image, HTTP 200, Bulkowski smoke PASS 4/4.
"""

from __future__ import annotations

from src.infrastructure.config.settings import Settings


def test_openrouter_vision_default_is_gemini_35_flash_lite() -> None:
    field = Settings.model_fields["ai_model_openrouter_vision"]
    assert field.default == "google/gemini-3.5-flash-lite"
