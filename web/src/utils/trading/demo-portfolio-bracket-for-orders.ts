import { isDemoPortfolioSnapshot } from '@/types/tradingBarrel';

/**
 * Demo Órdenes tab: SL/TP cells when fills omit per-order bracket (portfolio-level bracket).
 */
export function demoPortfolioBracketSlTpForOrders(portfolio: Record<string, unknown> | undefined): {
  sl: string | null;
  tp: string | null;
} {
  if (portfolio == null || !isDemoPortfolioSnapshot(portfolio)) {
    return { sl: null, tp: null };
  }

  return {
    sl: portfolio.bracket_stop_loss_usd ?? null,
    tp: portfolio.bracket_take_profit_usd ?? null,
  };
}
