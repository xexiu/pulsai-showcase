/**
 * Training job + model display helpers (SoT for admin/training UI).
 * Split from core.ts — keep sections ≤400 lines per CODING_STANDARDS.
 */

// ============================================================================
// Training Job Constants
// ============================================================================

export const TRAINING_STATUSES = {
  PENDING: 'pending',
  VALIDATING: 'validating',
  RUNNING: 'running',
  PAUSED: 'paused',
  COMPLETED: 'completed',
  /** Pipeline finished; validation gate blocked promotion (API mapper; DB still `completed`). */
  COMPLETED_NOT_PROMOTED: 'completed_not_promoted',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export type TrainingStatus = (typeof TRAINING_STATUSES)[keyof typeof TRAINING_STATUSES];

const ADMIN_DISPLAY_STATUSES = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  PRODUCTION: 'production',
  STAGING: 'staging',
} as const;

export type AdminDisplayStatus =
  (typeof ADMIN_DISPLAY_STATUSES)[keyof typeof ADMIN_DISPLAY_STATUSES];

export const STATUS_BADGE_VARIANT: Record<
  string,
  'default' | 'success' | 'warning' | 'danger' | 'info'
> = {
  [ADMIN_DISPLAY_STATUSES.PENDING]: 'warning',
  [ADMIN_DISPLAY_STATUSES.RUNNING]: 'info',
  [ADMIN_DISPLAY_STATUSES.COMPLETED]: 'success',
  [ADMIN_DISPLAY_STATUSES.FAILED]: 'danger',
  [ADMIN_DISPLAY_STATUSES.PRODUCTION]: 'success',
  [ADMIN_DISPLAY_STATUSES.STAGING]: 'default',
};

const RESERVED_MODEL_TAGS = [
  'production',
  'rollback',
  'best-sharpe',
  'best-accuracy',
  'validation-gate-passed',
] as const;

export function getCustomModelTags(tags: string[] | undefined): string[] {
  if (!tags || tags.length === 0) {
    return [];
  }

  const reserved = new Set<string>(RESERVED_MODEL_TAGS);

  return tags.filter((tag) => !reserved.has(tag));
}

export function formatModelVersion(version: number, displayVersion?: string): string {
  if (displayVersion) {
    return displayVersion;
  }

  return `v${version}`;
}

/**
 * Sort a model array by version descending (newest first).
 * Returns a new array — does not mutate the input.
 * SoT: both useModels.getModelOptions and MetaLabelingFields use this.
 */
export function sortModelsByVersionDesc<T extends { version: number }>(models: T[]): T[] {
  return [...models].sort((a, b) => b.version - a.version);
}

/**
 * Map backend model_type prefix to display name (SoT for architecture label).
 * Extend when adding LSTM, GRU, RF, Transformer, etc. (see sprint 3.1b).
 */
const MODEL_ARCHITECTURE_DISPLAY: Record<string, string> = {
  xgboost: 'XGBoost',
  lstm: 'LSTM',
  gru: 'GRU',
  transformer: 'Transformer',
  rf: 'Random Forest',
  random_forest: 'Random Forest',
  lightgbm: 'LightGBM',
} as const;

/**
 * Human-readable architecture name for dropdowns/labels from model_type.
 * Backend model_type: xgboost_3class, lstm_3class, etc. Future: LSTM, GRU, RF, Transformer.
 */
export function formatModelTypeToArchitectureName(modelType: string | null | undefined): string {
  if (!modelType || typeof modelType !== 'string') {
    return 'XGBoost';
  }

  const normalized = modelType.toLowerCase().trim();
  const prefix = normalized.split(/[_-]/)[0] ?? '';

  return (
    MODEL_ARCHITECTURE_DISPLAY[prefix] ??
    MODEL_ARCHITECTURE_DISPLAY[normalized] ??
    (prefix ? prefix.charAt(0).toUpperCase() + prefix.slice(1) : 'Model')
  );
}

/**
 * Human-readable model type for dropdowns and labels (3-class, 2-class BUY/SELL, regression).
 * Backend model_type: xgboost_3class, xgboost_2class_buy, xgboost_regression, etc.
 */
export function formatModelTypeForDisplay(modelType: string | null | undefined): string {
  if (!modelType || typeof modelType !== 'string') {
    return '3-class';
  }

  const normalized = modelType.toLowerCase().trim();

  if (normalized.includes('regression')) {
    const arch = formatModelTypeToArchitectureName(modelType);

    return `${arch} Regression`;
  }

  if (normalized.includes('2class') || normalized.includes('2_class')) {
    if (normalized.includes('buy')) return '2-class BUY';
    if (normalized.includes('sell')) return '2-class SELL';

    return '2-class';
  }

  return '3-class';
}
