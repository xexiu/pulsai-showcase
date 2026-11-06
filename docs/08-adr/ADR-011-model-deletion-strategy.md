# ADR-011: Model Deletion Strategy

## Status

**APPROVED** - 2026-01-30 | **IMPLEMENTED** - Sprint 2.9a (purge endpoint, auto-GC Celery task, 180-day retention)

## Context

The admin Models page (`/admin/models`) displays all ML models grouped by symbol/timeframe. Currently there is no way to delete old, failed, or unwanted models. As the system accumulates models over time, admins need a way to clean up.

### Key Considerations

1. **Financial Compliance** - Trading platforms require audit trails. Regulators may ask about historical models.
2. **Storage** - Each XGBoost model is ~50MB. Without cleanup, storage grows indefinitely.
3. **Safety** - Accidental deletion of a good model is costly (retraining takes hours).
4. **Recovery** - Mistakes happen. Admins may want to restore deleted models.

## Decision

Implement **HYBRID deletion strategy** with soft delete by default and optional hard purge.

### Deletion Rules

| Model State                  | Can Delete?         | Delete Type | Notes               |
| ---------------------------- | ------------------- | ----------- | ------------------- |
| **Currently production**     | ❌ BLOCKED          | N/A         | Must demote first   |
| **Was ever production**      | ⚠️ Super Admin only | Soft delete | Keep for compliance |
| **Staging (never promoted)** | ✅ Admin            | Soft delete | 180-day retention   |
| **Soft-deleted > 180 days**  | ✅ Auto             | Hard purge  | Background job      |

### Implementation

#### 1. Metadata Schema Update

```python
# ModelMetadata additions
deleted_at: datetime | None = None
deleted_by: str | None = None  # user_id for audit
was_ever_production: bool = False  # Set when promoted, never unset
```

#### 2. API Endpoints

```python
# Soft delete a model
DELETE /admin/models/{symbol}/{timeframe}/{version}
Request: { "confirm": true }
Response: { "deleted_at": "...", "can_restore_until": "..." }

# Restore a soft-deleted model (within 180 days)
POST /admin/models/{symbol}/{timeframe}/{version}/restore
Response: { "restored": true }
```

#### 3. UI Components

- **Delete button** on ModelRow (staging only, not production)
- **ConfirmModal** with warning text
- **Audit log entry** in `/admin/audit`
- **Deleted models filter** (show/hide deleted)

#### 4. Background Job (Celery)

```python
# Daily cleanup: hard delete models soft-deleted > 180 days
@celery.task
def purge_old_deleted_models():
    cutoff = datetime.now() - timedelta(days=180)
    # Find soft-deleted models older than cutoff
    # Hard delete files + metadata
    # Log to audit
```

### Safeguards

1. **Production block** - API rejects deletion of production models
2. **Confirmation required** - `confirm: true` in request body
3. **Audit logging** - Every delete/restore logged with user_id
4. **Super Admin for ex-production** - Only super_admin can delete models that were ever production

## Consequences

### Positive

- ✅ Admins can clean up failed/old models
- ✅ Full audit trail for compliance
- ✅ Recovery possible within 180 days
- ✅ Storage managed via auto-purge
- ✅ Production models protected

### Negative

- ❌ Soft-deleted models still consume storage for 180 days
- ❌ Queries need to filter out deleted models
- ❌ Slight complexity in model listing logic

### Neutral

- 180-day retention is configurable via environment variable

## Alternatives Considered

### A. Hard Delete Only

**Rejected** - Too risky for financial platform. No recovery, no audit trail.

### B. Soft Delete Forever

**Rejected** - Storage grows indefinitely. No practical cleanup mechanism.

### C. Archive to Cold Storage

**Considered for future** - Move old models to S3 Glacier instead of deletion. Good for very large scale. Not needed for MVP.

## Implementation Plan

1. **Phase 1**: Add `deleted_at`, `deleted_by` to ModelMetadata
2. **Phase 2**: Add DELETE API endpoint with safeguards
3. **Phase 3**: Add Delete button + ConfirmModal to UI
4. **Phase 4**: Add restore endpoint
5. **Phase 5**: Add Celery job for auto-purge

## References

- `/admin/models` page: `apps/web/src/app/[locale]/admin/models/page.tsx`
- ModelStorage: `apps/api/src/infrastructure/ml/model_storage.py`
- AuditService: `apps/api/src/application/services/audit_service.py`
