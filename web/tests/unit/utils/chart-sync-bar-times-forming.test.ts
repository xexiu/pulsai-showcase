// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { syncOverlayTimesWithFormingCandle } from '@/utils/chart-sync-bar-times';

describe('syncOverlayTimesWithFormingCandle', () => {
  it('returns a copy when forming time is absent', () => {
    const overlay = [{ time: 100 }, { time: 200 }];

    expect(syncOverlayTimesWithFormingCandle(overlay, null)).toEqual(overlay);
  });

  it('aligns the last overlay bar to the forming candle chart time', () => {
    const overlay = [{ time: 100 }, { time: 200 }];

    expect(syncOverlayTimesWithFormingCandle(overlay, 260)).toEqual([{ time: 100 }, { time: 260 }]);
  });

  it('does not move the last bar backward when forming time is older', () => {
    const overlay = [{ time: 100 }, { time: 200 }];

    expect(syncOverlayTimesWithFormingCandle(overlay, 150)).toEqual(overlay);
  });
});
