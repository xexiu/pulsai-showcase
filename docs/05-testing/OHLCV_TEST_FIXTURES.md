# OHLCV recorded test fixtures

Committed exchange candles for **deterministic, network-free** integration tests (features, warmup, chart surface, ML feature-path parity).

## Success criteria

| Criterion                            | Validation                                                              |
| ------------------------------------ | ----------------------------------------------------------------------- |
| No Binance/ccxt in CI pytest         | Integration tests load JSON only                                        |
| Same fetch path as production        | `scripts/record_ohlcv_fixture.py` uses `OHLCVFetcher.from_settings`     |
| All alignment TFs                    | Six files `btc_usdt_{5m,15m,30m,1h,4h,1d}_500.v1.json`                  |
| Indicator regression guard           | `feature_snapshot.fingerprints` per file                                |
| Model-column fingerprints (Phase 2)  | `model_feature_snapshot.fingerprints` per file                          |
| ML live vs backtest features         | `test_ml_inference_feature_path_parity_fixtures.py`                     |
| Frozen mini-ML predict/predict_proba | `test_ml_pinned_inference_parity_fixtures.py`                           |
| Manifest                             | `scripts/check_test_fixtures_manifest.py` + `test_fixtures_manifest.py` |

## Layout

```
apps/api/tests/fixtures/ohlcv/
  btc_usdt_5m_500.v1.json
  btc_usdt_15m_500.v1.json
  ...
apps/api/tests/fixtures/ml/
  pinned_inference_expectations.v1.json
  btc_usdt_1h/xgboost_3class_pinned_mini/v1/
    model.joblib          # ~120 KB — committed (gitignore exception); not production-scale
    metadata.json
    features.json
apps/api/src/shared/constants/ohlcv_test_fixtures.py   # SoT ids
apps/api/src/shared/constants/test_fixtures_manifest.py
apps/api/scripts/record_ohlcv_fixture.py
```

**`model.joblib` in git:** Global `*.joblib` ignores production artifacts (MB–GB). The pinned mini bundle under `tests/fixtures/ml/` is whitelisted so CI can run `test_ml_pinned_inference_parity_fixtures.py` without calling `freeze_pinned_ml_inference_fixture.py`. Regenerate locally after changing freeze hyperparameters.

## Record or refresh (maintainer, not CI)

```bash
cd apps/api && python scripts/record_ohlcv_fixture.py --all-alignment
cd apps/api && python scripts/enrich_ohlcv_fixture_model_snapshots.py --all-alignment
cd apps/api && python scripts/freeze_pinned_ml_inference_fixture.py
```

## Related tests

| Module                                              | Purpose                                                                                                                          |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `test_recorded_ohlcv_fixture_features.py`           | Chart-surface fingerprints per TF                                                                                                |
| `test_recorded_ohlcv_model_feature_fingerprints.py` | Model-column fingerprints per TF                                                                                                 |
| `test_recorded_ohlcv_calculate_path_invariants.py`  | calculate_all vs calculate_selected per group (`@pytest.mark.slow`; excluded from CI `backend-test`, run locally or full verify) |
| `test_ml_inference_feature_path_parity_fixtures.py` | Live vs backtest feature dict                                                                                                    |
| `test_ml_pinned_inference_parity_fixtures.py`       | predict/predict_proba direct vs live vs batch                                                                                    |
| `test_inference_path_compare.py`                    | Window slicing (synthetic)                                                                                                       |
| `test_feature_path_diff.py`                         | Unit-level path agreement                                                                                                        |

See also [FEATURE_CALC_PERFORMANCE_POLICY.md](../02-technical/FEATURE_CALC_PERFORMANCE_POLICY.md).

Last updated: 2026-05-25
