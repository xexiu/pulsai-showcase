"""
TDD [t21] — ModelMetadata.exchange field (Phase 1b, model-exchange provenance).

WHY THIS TEST EXISTS (behavior, not implementation):
- The supervisor WILL refuse to serve a model trained on exchange X with live
  bars from exchange Y once Phase 2 lands. That invariant requires
  ModelMetadata to *know* which exchange its bundle was trained on.
- Today `apps/api/models/*/*/v*/metadata.json` has NO `exchange` field, and
  `ModelMetadata` in `src/infrastructure/ml/model_metadata.py` has no such
  attribute either — see Phase 1b in
  `.cursor/plans/live_signal_latency_fix_8d8170ab.plan.md`.
- This test is a RED test first: it must FAIL against the current code and PASS
  after the Phase 1b GREEN change adds the field with a `"binance"` default.

CONTRACT under test:
1. `ModelMetadata` exposes an `exchange: str` attribute.
2. Default is `"binance"` (the historical reality for every shipped production
   model; see `registry.json` + `DEFAULT_EXCHANGE` in
   `src/shared/constants/trading.py:15`).
3. Old metadata.json dicts (no `exchange` key) still load without raising —
   the 72+ existing bundles on disk must keep working.
4. Round-trip (`to_dict` → `from_dict`) preserves the value, including
   non-default exchanges like `"bitget"`.
5. When `exchange` equals the default, `to_dict()` still emits it (defaults
   are not excluded — only `None`s are via `exclude_none=True`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest


def _minimal_kwargs() -> dict[str, Any]:
    """Shared minimal-required-fields factory. Keeps tests DRY."""
    return {
        "version": 1,
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "created_at": datetime.now(UTC),
        "training_samples": 10_000,
        "validation_folds": 5,
        "best_params": {"n_estimators": 100},
        "metrics": {"accuracy": 0.85},
        "feature_columns": ["rsi_14"],
    }


class TestModelMetadataExchangeField:
    """[t21] Exchange provenance on ModelMetadata — Phase 1b guardrail."""

    def test_exchange_defaults_to_binance(self) -> None:
        """Default must be 'binance' for historical/SoT alignment.

        WHY 'binance' and not None: every existing production model in
        `apps/api/models/registry.json` was trained via
        `DEFAULT_EXCHANGE = Exchange.BINANCE.value`
        (`src/shared/constants/trading.py:15`). Treating old bundles as
        Binance-trained is the only safe assumption — it mirrors reality
        AND keeps the Phase 2 cross-exchange barrier deterministic.
        """
        from src.infrastructure.ml.model_metadata import ModelMetadata

        metadata = ModelMetadata(**_minimal_kwargs())

        assert metadata.exchange == "binance"

    def test_exchange_accepts_non_default_value(self) -> None:
        """Must allow bitget (and any CCXT exchange id) at construction time.

        WHY: Phase 2 adds a Bitget supervisor. Models retrained on Bitget
        data MUST be able to declare that provenance or the Phase 2
        barrier will misclassify them as Binance.
        """
        from src.infrastructure.ml.model_metadata import ModelMetadata

        metadata = ModelMetadata(**_minimal_kwargs(), exchange="bitget")

        assert metadata.exchange == "bitget"

    def test_from_dict_backward_compatible_without_exchange_key(self) -> None:
        """Loading a PRE-Phase-1b metadata.json must NOT raise.

        WHY: 72+ bundles on disk (see `apps/api/models/`) were written
        before this field existed. `from_dict` MUST fill the Binance
        default transparently so inference continues to work the moment
        Phase 1b ships — no migration ordering foot-gun.
        """
        from src.infrastructure.ml.model_metadata import ModelMetadata

        old_payload = {
            "version": 34,
            "symbol": "BTC/USDT",
            "timeframe": "5m",
            "created_at": datetime.now(UTC).isoformat(),
            "training_samples": 12_000,
            "validation_folds": 5,
            "best_params": {},
            "metrics": {},
            "feature_columns": ["rsi_14"],
            "model_type": "xgboost_3class",
        }

        metadata = ModelMetadata.from_dict(old_payload)

        assert metadata.exchange == "binance"

    def test_exchange_roundtrip_non_default(self) -> None:
        """to_dict → from_dict must preserve non-default exchange.

        WHY: Data integrity contract. If we lose the exchange on disk
        we lose cross-exchange safety — a Bitget-trained model could
        silently be re-loaded as Binance-trained and fed Binance bars.
        """
        from src.infrastructure.ml.model_metadata import ModelMetadata

        original = ModelMetadata(**_minimal_kwargs(), exchange="bitget")

        restored = ModelMetadata.from_dict(original.to_dict())

        assert restored.exchange == "bitget"

    def test_exchange_appears_in_to_dict_even_for_default(self) -> None:
        """to_dict() must emit exchange even when it's the 'binance' default.

        WHY different from batch_id/holding_periods (which use exclude_none=True
        to stay omitted): exchange has a NON-None default, so Pydantic with
        exclude_none=True will still include it. This test locks in that
        behaviour so backfilled files are self-describing and inspectable
        (no 'is this value missing or defaulted?' ambiguity for ops).
        """
        from src.infrastructure.ml.model_metadata import ModelMetadata

        metadata = ModelMetadata(**_minimal_kwargs())

        data = metadata.to_dict()

        assert "exchange" in data
        assert data["exchange"] == "binance"

    @pytest.mark.parametrize("exchange_value", ["binance", "bitget"])
    def test_exchange_matches_domain_enum_values(self, exchange_value: str) -> None:
        """Accepted exchange strings must match the Exchange enum values exactly.

        WHY the enum (not a free string): `src/domain/enums.py:164` Exchange
        values MUST equal CCXT exchange IDs — any drift = runtime KeyError
        when CCXT resolves the exchange class. Enforcing enum-parity here
        means `metadata.exchange` can always be passed straight to CCXT/Pro.
        """
        from src.domain.enums import Exchange
        from src.infrastructure.ml.model_metadata import ModelMetadata

        valid_values = {e.value for e in Exchange}
        assert exchange_value in valid_values

        metadata = ModelMetadata(**_minimal_kwargs(), exchange=exchange_value)

        assert metadata.exchange in valid_values
