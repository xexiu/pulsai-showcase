import { formatPrice } from '@/utils/formatters/currency';

/** USD bracket price for portfolio / orders tables, or "-" when unset. */
export function formatBracketUsdDisplay(raw: string | null | undefined): string {
  if (raw == null) {
    return '-';
  }

  const s = String(raw).trim();

  if (s === '') {
    return '-';
  }

  const n = Number.parseFloat(s);

  if (!Number.isFinite(n)) {
    return '-';
  }

  return formatPrice(n);
}
