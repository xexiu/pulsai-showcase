# ADR-007: Admin Training Config Upload

## Status

**DEFERRED** - 2026-01-29

## Context

During Sprint 1.5b development, the question arose: should we add a JSON config upload option to the admin training screen?

### Current Implementation

- Training is **admin-only** (`/admin/training`)
- Admin configures via UI dropdowns: symbol, timeframe, trials, mode, days of data, model type, window, objective
- No way to import/export training configurations

### Proposed Feature

Extend admin training screen to:

1. Add "Upload Config" button to import JSON configuration
2. Add "Export Config" button to save current form state
3. Backend validates uploaded JSON against schema
4. Allow sharing configs between admins

### Example JSON Config

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "mode": "thorough",
  "nTrials": 200,
  "daysOfData": 365,
  "modelType": "xgboost_3class",
  "trainingWindow": 90,
  "objective": "sharpe_ratio",
  "version": "1.0"
}
```

## Analysis

### Pros

| Benefit             | Impact                                         |
| ------------------- | ---------------------------------------------- |
| **Config Sharing**  | Admins can share successful configs            |
| **Reproducibility** | Exact config saved for audit trail             |
| **Batch Training**  | Future: upload multiple configs for batch jobs |
| **Backup/Restore**  | Save configs before experiments                |

### Cons / Risks

| Risk                      | Severity  | Notes                                                         |
| ------------------------- | --------- | ------------------------------------------------------------- |
| **Validation complexity** | 🟡 MEDIUM | Must validate JSON against current model types, symbols, etc. |
| **Version mismatches**    | 🟡 MEDIUM | Config from v1.0 may not work in v2.0                         |
| **Edge case handling**    | 🟢 LOW    | What if uploaded symbol isn't supported?                      |

### Required Work

1. **Valibot schema** for config validation
2. **Version field** in config for forward compatibility
3. **Export button** + download as JSON
4. **Upload button** + file picker + validation
5. **Error messages** for invalid configs

**Estimated effort**: 2-3 days

## Decision

**DEFER to Phase 2 (post-MVP)**

### Rationale

For MVP, the UI dropdowns are sufficient:

- Only 1-2 admins using the system initially
- Can manually configure in < 1 minute
- No need for config sharing yet

### When to Implement

Implement when:

- Multiple admins need to share configurations
- Batch training is needed
- Audit requirements demand config versioning

## Consequences

### Positive

- Simpler MVP
- Less validation code to maintain
- Focus on core training functionality

### Negative

- Manual re-entry of configs for repeated experiments
- No config versioning/audit trail

### Mitigations

- Training configs are already logged in DB (`training_jobs` table)
- Can extract configs from DB if needed

## Decision Date

2026-01-29

## Decision Makers

- Main Architect (PulsAI)
