/**
 * Display Stripe subscription `current_period_end` (Unix seconds) in the user locale.
 */

import { formatDateTime } from '@/utils/formatters';

export function formatStripePeriodEndUnix(seconds: number | null): string {
  if (seconds == null) {
    return '';
  }

  return formatDateTime(new Date(seconds * 1000));
}
