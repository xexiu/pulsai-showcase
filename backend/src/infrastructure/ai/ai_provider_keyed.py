"""The constructor five keyed AI providers had written out five times, byte for byte.

REUSE-AUDIT: this lived in `ai_provider_base.py` for one commit and moved out immediately, because
adding it pushed that file to 435 lines against the 400-line standard (CODING_STANDARDS section 7).
Re-recording the baseline would have blessed a violation of the standard rather than met it, and
`ai_provider_base.py` is already five concerns wide -- language config, disclaimers, the system
prompt, the upstream error, and the two ABCs -- so a sixth made it worse. Considered putting the
logic on `AIProvider` itself: that would force `MockAIProvider`, which has no key, to inherit a
key-resolution contract it cannot satisfy, which is the ISP violation the AIProvider /
VisionAIProvider split exists to avoid.

CLONE CHECK, read before writing this (clone_body_guard, `apps/api/src/infrastructure/ai`,
min_similarity 0.85): five clusters live here -- `explain_signal` at 1.00 across claude/gemini/
groq/together, `_classify_sync` at 1.00 and `_call_api` at 0.94 across openrouter/together, and
`_init_client` at 1.00 plus `_call_vision_api` at 0.89 between `ai_provider_claude.py` and
`claude_client.py`. None of them is a constructor, so none covers this; they are the remaining
slices of the same paydown and are tracked separately.

MEASURED 2026-09-06, `find_clones` over `apps/api/src` at min_similarity 0.9: the five `__init__`
of claude / gemini / groq / openrouter / together formed ONE cluster at similarity **1.00**. They
differed only in which settings attribute held the key, which held the model, and the wording of
the not-configured warning.

THE FAILURE THIS PREVENTS, which is the only reason to introduce a pattern at all
(ARCHITECTURE_PATTERNS section 9, "pattern-as-explanation"): a sixth provider gets added by copying
the fifth, and any fix to key validation lands in four files out of five. The empty-string check is
exactly that kind of rule -- it exists because ``api_key=""`` must be an error rather than a silent
fallback to settings -- and it was duplicated five times.

A mixin rather than a base class, deliberately. ``AIProvider`` and ``VisionAIProvider`` already
split the hierarchy by capability; construction is orthogonal to whether a provider can see
images, so folding it into either would force the other to inherit it.

ORDERING IS LOAD-BEARING, and it is why this stayed duplicated. ``_init_client()`` is called from
inside the constructor, and the vision providers read ``self._vision_model`` when they build their
client. So subclasses set their own attributes BEFORE delegating here, and this method touches
nothing after ``_init_client``.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)

__all__ = ["KeyedAIProviderMixin"]


class KeyedAIProviderMixin:
    """Resolve an API key and model from settings, validate them, and build the client."""

    #: Settings attribute holding the API key. Named rather than passed so a subclass declares
    #: its configuration surface in one readable place instead of inside a constructor body.
    _API_KEY_SETTING: ClassVar[str]
    #: Settings attribute holding the default model id.
    _MODEL_SETTING: ClassVar[str]
    #: How this provider is named in the "cannot be empty" error the callers assert on.
    _KEY_LABEL: ClassVar[str]
    #: The not-configured warning, verbatim. Kept per provider because most carry a signup URL
    #: and Claude deliberately carries none.
    _NOT_CONFIGURED_WARNING: ClassVar[str]

    _api_key: str | None
    _model: str
    _client: Any

    def _configure_key_and_model(self, api_key: str | None) -> None:
        """Resolve key + model from settings, validate, and build the client when configured."""
        self._api_key = api_key if api_key is not None else getattr(settings, self._API_KEY_SETTING)

        # An EMPTY STRING is a misconfiguration, not "use the default". Passing None means
        # "read settings"; passing "" means someone wired an unset env var straight through.
        if api_key == "":
            raise ValueError(f"{self._KEY_LABEL} API key cannot be empty")

        self._model = getattr(settings, self._MODEL_SETTING)
        self._client = None

        if self._api_key:
            self._init_client()
        else:
            logger.warning(self._NOT_CONFIGURED_WARNING)

    def _init_client(self) -> None:
        """Build the vendor SDK client. Every keyed provider overrides this."""
        raise NotImplementedError
