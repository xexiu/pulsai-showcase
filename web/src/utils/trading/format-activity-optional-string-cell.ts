import { TRADING_BALANCE_UNAVAILABLE_MARK } from '@/utils/constants/trading';

/** Table cell for nullable API strings (amounts, limit). */
export function formatActivityOptionalStringCell(value: string | null | undefined): string {
  if (value == null || value === '') {
    return TRADING_BALANCE_UNAVAILABLE_MARK;
  }

  return value;
}
