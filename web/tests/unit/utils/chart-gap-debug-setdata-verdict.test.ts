// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { analyzeBarTimes, resolveSetDataGapCulprit } from '@/utils/chart-gap-debug';

describe('resolveSetDataGapCulprit', () => {
  it('flags LWC series gaps after prepare even when UTC source is contiguous', () => {
    const periodSec = 300;
    const utcTimes = [1_000_000, 1_000_300, 1_000_900];
    const utcAnalysis = analyzeBarTimes(utcTimes, periodSec);
    const displayTimes = utcTimes;
    const displayAnalysis = analyzeBarTimes(displayTimes, periodSec);
    const lwcTimes = [1_000_000, 1_000_900];
    const lwcAnalysis = analyzeBarTimes(lwcTimes, periodSec);

    expect(utcAnalysis.timeGapCount).toBe(1);
    expect(lwcAnalysis.timeGapCount).toBe(1);

    const culpritWithHoleyUtc = resolveSetDataGapCulprit(
      utcAnalysis,
      displayAnalysis,
      { droppedInvalidCount: 0, duplicateTimeCount: 0, lwcBarCount: 2 },
      lwcAnalysis
    );

    expect(culpritWithHoleyUtc).toBe('BE_OHLCV_TIMESTAMP_GAPS');

    const contiguousUtc = analyzeBarTimes([1_000_000, 1_000_300, 1_000_600], periodSec);
    const culpritLwcHoles = resolveSetDataGapCulprit(
      contiguousUtc,
      contiguousUtc,
      { droppedInvalidCount: 1, duplicateTimeCount: 0, lwcBarCount: 2 },
      lwcAnalysis
    );

    expect(culpritLwcHoles).toBe('FE_LWC_SERIES_GAPS');
  });
});
