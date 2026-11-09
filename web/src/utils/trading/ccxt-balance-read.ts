/**
 * CCXT unified `fetch_balance()` shape: `{ [code]: { free, used, total } }`.
 * Shared by preset capital (positive-only) and portfolio presentation (zero allowed).
 *
 * Asset keys are matched case-insensitively — aligned with
 * `apps/api/src/domain/services/ccxt_unified_balance_free.py` (venues vary in casing).
 */

import { TRADING_NUMERIC_EPSILON } from '@/utils/constants/trading';

type CcxtFreeBalance = { free?: number | string; total?: number | string };

function parseFinitePositive(raw: unknown): number | null {
  const n = typeof raw === 'number' ? raw : Number.parseFloat(String(raw ?? '').trim());

  if (!Number.isFinite(n) || n < TRADING_NUMERIC_EPSILON) {
    return null;
  }

  return n;
}

function isCcxtCurrencyRow(value: unknown): value is CcxtFreeBalance {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Resolve one currency row from unified balance — case-insensitive asset code.
 */
function getCcxtBalanceRow(
  balance: Record<string, unknown> | undefined,
  asset: string
): CcxtFreeBalance | null {
  if (!balance || typeof balance !== 'object' || !asset) {
    return null;
  }

  const target = asset.toUpperCase();

  for (const [key, value] of Object.entries(balance)) {
    if (String(key).toUpperCase() !== target) {
      continue;
    }

    if (!isCcxtCurrencyRow(value)) {
      return null;
    }

    return value;
  }

  return null;
}

/**
 * Quote/base **free** (or total) balance for presets — ignores zero and dust.
 */
export function readCcxtPositiveFreeBalance(
  balance: Record<string, unknown> | undefined,
  asset: string
): number | null {
  const row = getCcxtBalanceRow(balance, asset);

  if (row == null) {
    return null;
  }

  return parseFinitePositive(row.free ?? row.total);
}

/**
 * Display amount for portfolio lines — allows exactly zero when the exchange reports it.
 */
export function readCcxtUnifiedAssetAmount(
  balance: Record<string, unknown> | undefined,
  asset: string
): number | null {
  const row = getCcxtBalanceRow(balance, asset);

  if (row == null) {
    return null;
  }

  const raw = row.free ?? row.total;
  const n = typeof raw === 'number' ? raw : Number.parseFloat(String(raw ?? '').trim());

  if (!Number.isFinite(n) || n < 0) {
    return null;
  }

  return n;
}
