import { isPaperPortfolioSnapshot } from '@/types/tradingBarrel';

/**
 * IDs of open aggregate positions from GET /trading/portfolio (paper mode).
 * Used to surface linked filled swap orders on the Órdenes tab.
 */
export function extractOpenPaperPositionIdsFromPortfolio(
  portfolio: Record<string, unknown> | undefined
): ReadonlySet<string> {
  if (portfolio == null || !isPaperPortfolioSnapshot(portfolio)) {
    return new Set();
  }

  const out = new Set<string>();

  for (const row of portfolio.open_positions) {
    const pid = row.position_id?.trim();

    if (pid) {
      out.add(pid);
    }
  }

  return out;
}
