"""
TDD Tests for feature/training constants (SoT Phase 1.1).

DEFAULT_MAX_FEATURES and FEATURE_CORRELATION_THRESHOLD must live in shared/constants
so feature_selection, training_validation, config, and training pipelines use one source.
"""


class TestFeatureConstantsValues:
    """Test feature constants have expected values."""

    def test_default_max_features_is_25(self) -> None:
        """DEFAULT_MAX_FEATURES is 25 (ADR-014; prevents overfitting with 71 available features)."""
        from src.shared.constants import DEFAULT_MAX_FEATURES

        assert DEFAULT_MAX_FEATURES == 25

    def test_default_min_features_after_selection_is_3(self) -> None:
        """Post-feature-engineering floor avoids degenerate single-feature models (L1 collapse)."""
        from src.shared.constants import DEFAULT_MIN_FEATURES_AFTER_SELECTION

        assert DEFAULT_MIN_FEATURES_AFTER_SELECTION == 3

    def test_max_features_limit_is_50(self) -> None:
        """Hard cap on user-requested max_features. Overfitting guard: at 4h the minority
        class has ~300 samples, so 50 features ≈ 6 events/variable (the aggressive edge);
        100 would be ~3 EPV (overfit). The model self-selects ~14, so 50 never binds it."""
        from src.shared.constants import MAX_FEATURES_LIMIT

        assert MAX_FEATURES_LIMIT == 50

    def test_max_features_limit_at_least_default(self) -> None:
        """The hard cap must never sit below the default, else the default would be rejected."""
        from src.shared.constants import DEFAULT_MAX_FEATURES, MAX_FEATURES_LIMIT

        assert MAX_FEATURES_LIMIT >= DEFAULT_MAX_FEATURES

    def test_feature_correlation_threshold_is_0_85(self) -> None:
        """FEATURE_CORRELATION_THRESHOLD is 0.85 (tighter than v11's 0.95)."""
        from src.shared.constants import FEATURE_CORRELATION_THRESHOLD

        assert FEATURE_CORRELATION_THRESHOLD == 0.85

    def test_min_candles_for_backtest_matches_indicators(self) -> None:
        """MIN_CANDLES_FOR_BACKTEST aligns with indicator warmup (same as live signals)."""
        from src.shared.constants import MIN_CANDLES_FOR_BACKTEST, MIN_CANDLES_FOR_INDICATORS

        assert MIN_CANDLES_FOR_BACKTEST == MIN_CANDLES_FOR_INDICATORS
        assert MIN_CANDLES_FOR_BACKTEST == 100


class TestFeatureConstantsExported:
    """Test feature constants are exported from src.shared.constants."""

    def test_default_max_features_exported(self) -> None:
        """DEFAULT_MAX_FEATURES is in shared.constants __all__ or importable."""
        import src.shared.constants as sc

        assert hasattr(sc, "DEFAULT_MAX_FEATURES")

    def test_default_min_features_after_selection_exported(self) -> None:
        """DEFAULT_MIN_FEATURES_AFTER_SELECTION is importable from shared.constants."""
        import src.shared.constants as sc

        assert hasattr(sc, "DEFAULT_MIN_FEATURES_AFTER_SELECTION")

    def test_max_features_limit_exported(self) -> None:
        """MAX_FEATURES_LIMIT is importable from shared.constants (SoT for the FE hard cap)."""
        import src.shared.constants as sc

        assert hasattr(sc, "MAX_FEATURES_LIMIT")

    def test_feature_correlation_threshold_exported(self) -> None:
        """FEATURE_CORRELATION_THRESHOLD is in shared.constants __all__ or importable."""
        import src.shared.constants as sc

        assert hasattr(sc, "FEATURE_CORRELATION_THRESHOLD")

    def test_min_candles_for_backtest_exported(self) -> None:
        """MIN_CANDLES_FOR_BACKTEST is importable from shared.constants."""
        import src.shared.constants as sc

        assert hasattr(sc, "MIN_CANDLES_FOR_BACKTEST")
