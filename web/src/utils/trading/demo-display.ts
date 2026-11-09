/**
 * Demo trading display helpers — fee % and placeholders aligned with API `DEFAULT_FEE_RATE`.
 */

import { TRADING_DEMO_FEE_RATE_FRACTION } from '@/utils/constants/trading';
import { formatUsd2 } from '@/utils/formatters/currency';

const FEE_PERCENT = TRADING_DEMO_FEE_RATE_FRACTION * 100;

/** "0.10%" style label for demo fee (matches backend 0.001 fraction). */
export function getDemoTradingFeePercentLabel(): string {
  return `${FEE_PERCENT.toFixed(2)}%`;
}

/** Signed zero P&L placeholder until realized P&L is wired from API. */
export function formatDemoPnlPlaceholderUsd(): string {
  return `+${formatUsd2(0)}`;
}
