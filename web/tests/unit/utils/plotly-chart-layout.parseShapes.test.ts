// @vitest-environment node
/**
 * Plotly layout.shapes parsing — behavior tests for overlay merge (no loose casts at call sites).
 */

import { describe, expect, it } from 'vitest';

import type { PlotlyShape } from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';
import { parsePlotlyLayoutShapes } from '@/utils/plotly-chart-layout';

describe('parsePlotlyLayoutShapes', () => {
  it('returns empty when shapes missing or not an array', () => {
    expect(parsePlotlyLayoutShapes(undefined)).toEqual([]);
    expect(parsePlotlyLayoutShapes(null)).toEqual([]);
    expect(parsePlotlyLayoutShapes('x')).toEqual([]);
    expect(parsePlotlyLayoutShapes({})).toEqual([]);
  });

  it('keeps rect/line entries with xref and yref', () => {
    const valid: PlotlyShape = {
      type: 'line',
      xref: 'x',
      yref: 'y',
      x0: 'a',
      x1: 'b',
      y0: 1,
      y1: 2,
    };

    expect(parsePlotlyLayoutShapes([valid])).toEqual([valid]);
  });

  it('drops entries without shape discriminator or axis refs', () => {
    const valid: PlotlyShape = {
      type: 'rect',
      xref: 'x',
      yref: 'y',
      x0: 'a',
      x1: 'b',
      y0: 0,
      y1: 1,
    };

    expect(
      parsePlotlyLayoutShapes([valid, { foo: 1 }, { type: 'scatter' }, { type: 'line', xref: 'x' }])
    ).toEqual([valid]);
  });
});
