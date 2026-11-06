// =============================================================================
// Common Types - Shared across frontend and backend
// =============================================================================

import type { DEFAULT_SUPPORTED_SYMBOLS } from '../constants/symbol-registry';

/**
 * API Response wrapper for consistent response format
 */
export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  timestamp: string;
}

/**
 * Pagination params for list endpoints
 */
export interface PaginationParams {
  page: number;
  limit: number;
}

/**
 * Paginated response wrapper
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
  hasMore: boolean;
}

/**
 * Supported trading symbols — derived from the shared symbol registry, never re-typed.
 * The backend list (DEFAULT_SUPPORTED_SYMBOL_VALUES) is parity-tested against that registry.
 */
export type TradingSymbol = (typeof DEFAULT_SUPPORTED_SYMBOLS)[number];

/**
 * Supported timeframes for OHLCV data.
 * Must match BE settings.supported_timeframes (config API).
 */
// Mirrors the BE TIMEFRAME_REGISTRY keys (apps/api/src/shared/constants/timeframes.py). `2h`/`6h`
// joined it on 2026-08-12 as real training-band members; a TS union is compile-time so it cannot
// be fetched from /config/public, which is why this copy exists at all — see the drift test.
export type Timeframe =
  | '1m'
  | '5m'
  | '15m'
  | '30m'
  | '1h'
  | '2h'
  | '4h'
  | '6h'
  | '8h'
  | '12h'
  | '1d'
  | '3d'
  | '1w';

/**
 * Signal action types
 */
export type SignalAction = 'BUY' | 'SELL' | 'HOLD';

/**
 * Subscription tiers
 */
export type SubscriptionTier = 'free' | 'starter' | 'pro' | 'elite';

/**
 * User roles
 */
export const USER_ROLES = {
  SUPER_ADMIN: 'super_admin',
  ADMIN: 'admin',
  USER: 'user',
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];
