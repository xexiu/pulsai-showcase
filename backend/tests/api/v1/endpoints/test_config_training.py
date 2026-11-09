"""
Training Configuration Tests (TDD)

WHY this test:
- optimization_objectives were hardcoded in frontend ❌
- Should come from backend (single source of truth)
- Model-type aware (3-class vs 2-class vs regression)
- Future-proof: add new metrics without frontend changes

@see .cursorrules TDD requirement
@see docs/CONFIGURATION.md
"""

from typing import TYPE_CHECKING

from src.domain.enums import Exchange

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestTrainingConfigEndpoint:
    """Tests for /config/public training configuration."""

    def test_config_includes_training_section(self, client: TestClient) -> None:
        """
        /config/public MUST include training configuration.

        WHY: Frontend needs to know available objectives, model types, etc.
        """
        response = client.get("/api/v1/config/public")

        assert response.status_code == 200
        data = response.json()["data"]

        # Training section must exist
        assert "training" in data, "Missing 'training' section in config"

    def test_public_config_exposes_only_backend_supported_exchanges(
        self,
        client: TestClient,
    ) -> None:
        """
        /config/public MUST only expose exchanges supported across backend contracts.

        WHY:
        - FE treats this response as the source of truth
        - advertising OHLCVModel-only fallback exchanges as "supported" creates fail-open UX
        - the enum-backed exchange registry is the backend runtime contract
        """
        response = client.get("/api/v1/config/public")

        assert response.status_code == 200
        assert response.json()["data"]["exchanges"] == [exchange.value for exchange in Exchange]

    def test_public_config_includes_free_tier_allowed_symbols(self, client: TestClient) -> None:
        """
        /config/public MUST expose the exact free-tier symbol allowlist.

        WHY:
        - FE gating should consume backend policy directly (no symbol-order assumptions).
        - Product can change free-tier symbol policy via settings without FE redeploy.
        """
        response = client.get("/api/v1/config/public")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "free_tier_allowed_symbols" in data
        assert data["free_tier_allowed_symbols"] == ["BTC/USDT"]

    def test_training_config_has_optimization_objectives(self, client: TestClient) -> None:
        """
        Training config MUST include optimization_objectives per model type.

        WHY: Different model types need different metrics
        - 3-class and 2-class: the objectives calculate_metric scores
        - regression: regression_performance, the IC the regression trainers maximise
        """
        response = client.get("/api/v1/config/public")
        data = response.json()["data"]["training"]

        assert "optimization_objectives" in data
        objectives = data["optimization_objectives"]

        # Must be a dict keyed by model type
        assert isinstance(objectives, dict)
        assert len(objectives) > 0

    def test_3class_model_has_required_objectives(self, client: TestClient) -> None:
        """
        3-class classification models need these objectives.

        WHY: Research shows these are critical for trading:
        - accuracy: baseline (but causes class imbalance!)
        - f1_score: balances precision/recall
        - sharpe_ratio: risk-adjusted returns
        - profit_factor: win/loss ratio
        """
        response = client.get("/api/v1/config/public")
        objectives = response.json()["data"]["training"]["optimization_objectives"]

        # 3-class model objectives
        assert "xgboost_3class" in objectives
        three_class = objectives["xgboost_3class"]

        assert "accuracy" in three_class
        assert "f1_score" in three_class
        assert "sharpe_ratio" in three_class
        assert "profit_factor" in three_class

    def test_2class_model_has_required_objectives(self, client: TestClient) -> None:
        """
        2-class classification models get the classifier objectives, rank_ic included.

        ROC-AUC was offered here until 2026-10-22 and never scored: calculate_metric had no roc_auc
        branch and tuned those models on accuracy, so it is no longer offered.

        UPDATED (Sprint 2.0m): API now returns architecture-only types.
        "xgboost_2class" instead of "xgboost_2class_buy"/"xgboost_2class_sell".
        Direction (buy/sell) is selected separately via model_type_directions.
        """
        response = client.get("/api/v1/config/public")
        objectives = response.json()["data"]["training"]["optimization_objectives"]

        # NOTE: Now uses architecture-only key (Sprint 2.0m refactor)
        assert "xgboost_2class" in objectives
        two_class = objectives["xgboost_2class"]

        assert "accuracy" in two_class
        assert "f1_score" in two_class
        assert "rank_ic" in two_class
        assert "roc_auc" not in two_class

    def test_catboost_and_regression_models_share_complete_backend_objective_contract(
        self,
        client: TestClient,
    ) -> None:
        """Every exposed model type must have matching objectives, labels, and options."""
        response = client.get("/api/v1/config/public")
        training = response.json()["data"]["training"]

        objectives = training["optimization_objectives"]
        labels = training["objective_labels"]
        options = {item["value"] for item in training["objective_options"]}

        assert "catboost" in objectives
        assert "trading_performance" in objectives["catboost"]

        assert "xgboost_regression" in objectives
        assert "lightgbm_regression" in objectives
        assert "regression_performance" in objectives["xgboost_regression"]

        for objective_name in objectives["xgboost_regression"]:
            assert objective_name in labels
            assert objective_name in options

    def test_training_config_has_model_types(self, client: TestClient) -> None:
        """
        Config MUST list available model types.

        WHY: Frontend dropdown needs to know valid options.

        UPDATED (Sprint 2.0m): model_types now returns architecture-only types.
        Direction (buy/sell) is selected via separate model_type_directions dict.
        """
        response = client.get("/api/v1/config/public")
        data = response.json()["data"]["training"]

        assert "model_types" in data
        model_types = data["model_types"]

        # Architecture-only types (Sprint 2.0m refactor)
        assert "xgboost_3class" in model_types
        assert "xgboost_2class" in model_types

        # model_type_directions maps architecture → valid directions
        assert "model_type_directions" in data
        directions = data["model_type_directions"]
        assert "xgboost_2class" in directions
        assert "buy" in directions["xgboost_2class"]
        assert "sell" in directions["xgboost_2class"]

    def test_training_config_has_target_types(self, client: TestClient) -> None:
        """
        Config MUST list available target types.

        WHY: Dropdown for target creation method.

        UPDATED: target_types are fetched dynamically from TargetFactory.
        All registered TargetType enum values are returned dynamically.
        """
        response = client.get("/api/v1/config/public")
        data = response.json()["data"]["training"]

        assert "target_types" in data
        target_types = data["target_types"]

        # Core target types that must exist (from TargetFactory registry)
        assert "threshold" in target_types  # Basic fixed threshold
        assert "volatility" in target_types  # ATR-scaled threshold
        assert "binary" in target_types  # Simple binary classification

    def test_objectives_have_display_labels(self, client: TestClient) -> None:
        """
        Objectives should have display labels for UI.

        WHY: 'f1_score' → 'F1 Score (Balanced Classes)' for better UX.
        """
        response = client.get("/api/v1/config/public")
        data = response.json()["data"]["training"]

        # Labels for UI display
        assert "objective_labels" in data
        labels = data["objective_labels"]

        assert "accuracy" in labels
        assert "f1_score" in labels
        # Labels should be user-friendly
        assert "Accuracy" in labels["accuracy"] or "accuracy" in labels["accuracy"].lower()

    # =========================================================================
    # Sprint 2.0p: Training Default & Objective Changes
    # =========================================================================

    def test_trading_performance_in_3class_objectives(self, client: TestClient) -> None:
        """
        trading_performance MUST appear in 3-class model objectives.

        WHY: This is the recommended default for trading models.
        Uses RiskAdjustedTradingObjective (avg return + win rate + Sharpe - drawdown).

        Sprint 2.0p: Previously missing from classification_base list,
        which caused it to not appear in the dropdown.
        """
        response = client.get("/api/v1/config/public")
        objectives = response.json()["data"]["training"]["optimization_objectives"]

        three_class = objectives["xgboost_3class"]
        assert "trading_performance" in three_class

    def test_rank_ic_label_says_recommended(self, client: TestClient) -> None:
        """
        rank_ic (signal-quality) is the recommended default objective (P2.3): its label carries
        'Recommended'. trading_performance previously held it but was demoted — selecting on backtest
        net picked multiple-testing LUCK (inflated coin-flips, buried real signal), not skill.
        """
        response = client.get("/api/v1/config/public")
        labels = response.json()["data"]["training"]["objective_labels"]

        assert "rank_ic" in labels
        assert "Recommended" in labels["rank_ic"]
        assert "Recommended" not in labels.get("trading_performance", "")

    def test_accuracy_label_no_longer_says_default(self, client: TestClient) -> None:
        """
        accuracy label should NOT say 'Default' anymore.

        Sprint 2.0p: trading_performance is the new recommended default.
        Accuracy label changed from 'Accuracy (Default)' to 'Accuracy'.
        """
        response = client.get("/api/v1/config/public")
        labels = response.json()["data"]["training"]["objective_labels"]

        assert "accuracy" in labels
        # Should NOT contain '(Default)' — that's misleading now
        assert "Default" not in labels["accuracy"]

    def test_backtest_config_includes_exit_strategy_field_metadata(
        self,
        client: TestClient,
    ) -> None:
        """
        Backtest config MUST expose exit strategy parameter metadata.

        WHY:
        - FE should not hardcode which strategies need which parameter inputs
        - Adding a new strategy or changing its parameter set must be BE-driven
        - /config/public is already the single source of truth for dropdown options
        """
        response = client.get("/api/v1/config/public")
        backtest = response.json()["data"]["backtest"]

        assert "exit_strategy_fields" in backtest
        exit_strategy_fields = backtest["exit_strategy_fields"]

        assert exit_strategy_fields["fixed_holding"] == []
        assert exit_strategy_fields["raw_signal"] == []
        assert exit_strategy_fields["fixed_tpsl"] == [
            {"key": "stop_loss_pct", "default": None},
            {"key": "take_profit_pct", "default": None},
        ]
        assert exit_strategy_fields["risk_reward"] == [
            {"key": "stop_loss_pct", "default": None},
            {"key": "risk_reward_ratio", "default": 2.0},
        ]
        assert exit_strategy_fields["trailing_stop"] == [
            {"key": "stop_loss_pct", "default": None},
            {"key": "trail_activation_pct", "default": 1.0},
            {"key": "trail_pct", "default": 0.5},
        ]
        assert exit_strategy_fields["atr_based"] == [
            {"key": "atr_period", "default": 14},
            {"key": "atr_multiplier", "default": 2.0},
            {"key": "max_sl_pct", "default": None},
            {"key": "risk_reward_ratio", "default": 2.0},
        ]
        assert exit_strategy_fields["dynamic_tpsl"] == [
            {"key": "atr_period", "default": 14},
            {"key": "atr_multiplier", "default": 2.0},
            {"key": "max_sl_pct", "default": None},
            {"key": "risk_reward_ratio", "default": 2.0},
        ]
        assert exit_strategy_fields["min_profit_after_fees"] == [
            {"key": "min_net_pct", "default": 0.0},
        ]
        assert backtest["dynamic_tpsl_policy"] == {
            "low_vol_atr_pct_threshold": 0.5,
            "high_vol_atr_pct_threshold": 5.0,
            "low_vol_multiplier_scale": 1.5,
            "mid_vol_multiplier_scale": 1.0,
            "high_vol_multiplier_scale": 0.9,
            "min_sl_pct": 0.75,
            "max_sl_pct": 8.0,
            "regimes": ["low", "mid", "high"],
        }
