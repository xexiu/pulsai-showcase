/**
 * Parse a CCXT-style trading pair (e.g. "BTC/USDT") into base and quote assets.
 */
export type SymbolPair = {
  base: string;
  quote: string;
};

export function parseSymbolPair(symbol: string): SymbolPair {
  const trimmed = symbol.trim();

  if (!trimmed.includes('/')) {
    return { base: trimmed, quote: 'USDT' };
  }

  const [rawBase, rawQuote] = trimmed.split('/');
  const base = rawBase?.trim() ?? '';
  const quote = rawQuote?.trim() ?? '';

  return {
    base: base.length > 0 ? base : trimmed,
    quote: quote.length > 0 ? quote : 'USDT',
  };
}
