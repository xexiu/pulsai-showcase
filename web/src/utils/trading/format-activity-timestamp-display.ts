import { TRADING_BALANCE_UNAVAILABLE_MARK } from '@/utils/constants/trading';
import { formatDateTimeOrNull } from '@/utils/formatters/datetime';

/**
 * Activity table time cell: locale datetime or em dash (SoT: `TRADING_BALANCE_UNAVAILABLE_MARK`).
 */
export function formatActivityTimestampDisplay(iso: string | undefined | null): string {
  if (iso == null || iso === '') {
    return TRADING_BALANCE_UNAVAILABLE_MARK;
  }

  return formatDateTimeOrNull(iso) ?? TRADING_BALANCE_UNAVAILABLE_MARK;
}
