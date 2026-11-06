/**
 * Type declarations for Plotly.js custom bundles
 *
 * WHY this file:
 * - plotly.js-finance-dist-min doesn't ship with TypeScript types
 * - We declare the module to satisfy TypeScript
 * - The actual Plotly types come from @types/plotly.js (already installed)
 */

declare module 'plotly.js-finance-dist-min' {
  import Plotly from 'plotly.js';
  export default Plotly;
  export * from 'plotly.js';
}

declare module 'react-plotly.js/factory' {
  import type { ComponentType } from 'react';

  import type { PlotParams } from 'react-plotly.js';

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function createPlotlyComponent(plotly: any): ComponentType<PlotParams>;
  export default createPlotlyComponent;
}
