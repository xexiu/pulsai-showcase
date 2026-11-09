/**
 * Buying power for USD amount presets (paper trade): depends on mode, side, and portfolio snapshot.
 */

import {
  TRADING_DEMO_FALLBACK_BALANCE_USD_STRING,
  TRADING_NUMERIC_EPSILON,
} from '@/utils/constants/trading';
import { readCcxtPositiveFreeBalance } from '@/utils/trading/ccxt-balance-read';

function parseFinitePositive(raw: unknown): number | null {
  const n = typeof raw === 'number' ? raw : Number.parseFloat(String(raw ?? '').trim());

  if (!Number.isFinite(n) || n < TRADING_NUMERIC_EPSILON) {
    return null;
  }

  return n;
}

/** True when demo portfolio has no USD and no base (BTC) to trade — user should reset demo. */
export function isDemoPortfolioExhausted(portfolio: Record<string, unknown> | undefined): boolean {
  const usd = Number.parseFloat(String(portfolio?.['balance_usd'] ?? '0'));
  const btc = Number.parseFloat(String(portfolio?.['btc_balance'] ?? '0'));
  const hasUsd = Number.isFinite(usd) && usd > TRADING_NUMERIC_EPSILON;
  const hasBtc = Number.isFinite(btc) && btc > TRADING_NUMERIC_EPSILON;

  return !hasUsd && !hasBtc;
}

function presetCapitalDemoBuy(portfolio: Record<string, unknown> | undefined): number | null {
  const raw = portfolio?.['balance_usd'] ?? TRADING_DEMO_FALLBACK_BALANCE_USD_STRING;

  return parseFinitePositive(raw);
}

function presetCapitalDemoSell(
  portfolio: Record<string, unknown> | undefined,
  referencePriceUsd: number | null
): number | null {
  const btc = parseFinitePositive(portfolio?.['btc_balance']);

  if (btc == null || referencePriceUsd == null || referencePriceUsd <= 0) {
    return null;
  }

  return btc * referencePriceUsd;
}

function presetCapitalPaperBuy(
  portfolio: Record<string, unknown> | undefined,
  quote: string
): number | null {
  const bal = portfolio?.['balance'] as Record<string, unknown> | undefined;

  return readCcxtPositiveFreeBalance(bal, quote);
}

function presetCapitalPaperSell(
  portfolio: Record<string, unknown> | undefined,
  baseAsset: string,
  referencePriceUsd: number | null
): number | null {
  const bal = portfolio?.['balance'] as Record<string, unknown> | undefined;
  const baseFree = readCcxtPositiveFreeBalance(bal, baseAsset);

  if (baseFree == null || referencePriceUsd == null || referencePriceUsd <= 0) {
    return null;
  }

  return baseFree * referencePriceUsd;
}

/**
 * True when the portfolio has a positive free base balance to sell (demo: `btc_balance`;
 * paper: CCXT `balance[base].free`).
 */
export function hasSellableBasePosition(
  modeStr: string,
  portfolio: Record<string, unknown> | undefined,
  baseAsset: string
): boolean {
  if (modeStr === 'demo') {
    return parseFinitePositive(portfolio?.['btc_balance']) != null;
  }

  if (modeStr === 'paper') {
    const bal = portfolio?.['balance'] as Record<string, unknown> | undefined;

    return readCcxtPositiveFreeBalance(bal, baseAsset) != null;
  }

  return false;
}

/**
 * Max USD notional usable for preset fill: buy → quote (USDT) cash; sell → base * reference price.
 */
export function getPresetCapitalUsd(params: {
  modeStr: string;
  side: 'buy' | 'sell';
  portfolio: Record<string, unknown> | undefined;
  referencePriceUsd: number | null;
  quoteAsset?: string;
  baseAsset: string;
}): number | null {
  const { modeStr, side, portfolio, referencePriceUsd, baseAsset } = params;
  const quote = params.quoteAsset ?? 'USDT';

  if (modeStr === 'demo') {
    return side === 'buy'
      ? presetCapitalDemoBuy(portfolio)
      : presetCapitalDemoSell(portfolio, referencePriceUsd);
  }

  if (modeStr === 'paper') {
    return side === 'buy'
      ? presetCapitalPaperBuy(portfolio, quote)
      : presetCapitalPaperSell(portfolio, baseAsset, referencePriceUsd);
  }

  return null;
}

/** USD string for amount input from % of capital (2 decimal places). */
export function formatUsdAmountFromPercent(capitalUsd: number, percent: number): string {
  if (!Number.isFinite(capitalUsd) || capitalUsd <= 0) {
    return '';
  }

  if (!Number.isFinite(percent) || percent <= 0) {
    return '';
  }

  const usd = (capitalUsd * percent) / 100;

  return usd.toFixed(2);
}
