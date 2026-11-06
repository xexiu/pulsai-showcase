'use client';

/**
 * PlotlyWrapper - Proper initialization of Plotly with finance bundle
 *
 * WHY separate file:
 * - react-plotly.js factory needs synchronous Plotly instance
 * - Dynamic import in Next.js needs this pattern for custom bundles
 * - The finance bundle includes candlestick charts (basic bundle doesn't!)
 *
 * @see https://github.com/plotly/react-plotly.js#with-customised-plotlyjs
 */

// Use require for plotly.js bundles - they use UMD format

import Plotly from 'plotly.js-finance-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

// Create Plot component with finance bundle (includes candlestick, ohlc, etc.)
const Plot = createPlotlyComponent(Plotly);

export default Plot;
