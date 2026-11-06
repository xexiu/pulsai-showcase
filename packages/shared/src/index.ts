// =============================================================================
// @pulsai/shared - Shared Types and Utilities
// =============================================================================

// Export all shared types
export * from './types/common';
export * from './types/errors';
export * from './types/signals';
export * from './types/user';

// Export constants (centralized config)
export * from './constants';

// Export per-exchange config (yaml-mirrored, validated at module init)
export * from './exchanges';

// Export validators
export * from './validators/signals';

// Trading — outbound client order id policy (SoT; parity with API domain services)
export * from './trading/client-order-id';

// Utilities
export { parseSymbolPair, type SymbolPair } from './utils/parseSymbolPair';
