/**
 * Vitest Global Setup
 *
 * Runs before all tests.
 * Sets up testing-library matchers, global mocks, and test helpers.
 *
 * Global test setup with centralized mocks
 */

import { createElement } from 'react';

import { afterEach, vi } from 'vitest';

// DOM-only matchers (@testing-library/jest-dom) + component cleanup load lazily so
// node-env tests (`// @vitest-environment node`) skip the heavy @testing-library import.
if (typeof document !== 'undefined') {
  await import('@testing-library/jest-dom/vitest');
  const { cleanup, configure } = await import('@testing-library/react');

  // `waitFor` has its OWN 1000ms budget, independent of vitest's `testTimeout: 10000`. A test is
  // therefore allowed ten seconds to run but only one second to wait for a condition, and the
  // suite runs on 10 parallel workers — so a hook doing a real React Query round-trip can blow
  // the 1s bound on a saturated machine while being perfectly correct.
  //
  // MEASURED: useAdminModelsPage's "passes both filters" failed in every FULL run (expected
  // true to be false — `loading` had not flipped yet) and passed every time the file ran alone.
  // Not retries — `createTestQueryClient` already sets `retry: 0`, checked before assuming.
  //
  // A waitFor timeout bounds how long the MACHINE may take, not whether the code is right, so
  // raising it hides nothing: a genuinely stuck query still fails, just a few seconds later,
  // and still well inside `testTimeout`.
  configure({ asyncUtilTimeout: 5000 });

  afterEach(() => {
    cleanup();
  });
}

// =============================================================================
// Cleanup after each test
// =============================================================================

afterEach(() => {
  vi.clearAllMocks();
});

// =============================================================================
// Mock: next-intl (Internationalization)
// =============================================================================

// Translation map for common keys (PRO: Returns readable values, not just keys)
const translations: Record<string, string | ((values: Record<string, string | number>) => string)> =
  {
    // Landing page
    'landing.title': 'PulsAI - La plataforma más potente en señales de trading con IA',
    'landing.subtitle': 'Powered by Machine Learning',
    'landing.description': 'Get intelligent trading signals based on XGBoost ML models.',
    'landing.cta': 'Get Started',
    'landing.features.title': 'Features',
    'landing.features.signals.title': 'ML Signals',
    'landing.features.signals.description': 'Real-time trading signals powered by XGBoost.',
    'landing.features.sentiment.title': 'Sentiment Analysis',
    'landing.features.sentiment.description': 'Social media sentiment tracking.',
    'landing.features.portfolio.title': 'Portfolio Tracking',
    'landing.features.portfolio.description': 'Track your crypto portfolio performance.',

    // Landing - Newsletter
    'landing.newsletter.success': "You're on the list! We'll be in touch soon.",
    'landing.newsletter.emailAlreadySubscribed': (v) =>
      `The email ${v['email']} is on our system already. Please try another.`,
    'errors.genericWithRetry': 'Something went wrong. Please try again.',

    // Landing - Model Info
    'landing.modelInfo.title': 'Model Information',
    'landing.modelInfo.version': 'Version',
    'landing.modelInfo.accuracy7d': 'Accuracy (7d)',
    'landing.modelInfo.sharpeRatio': 'Sharpe Ratio',
    'landing.modelInfo.winRate': 'Win Rate',
    'landing.modelInfo.lastTrained': 'Last Trained',

    // Common
    'common.toggleTheme': 'Toggle theme',
    'common.selectLanguage': 'Select language',
    'common.signIn': 'Sign In',
    'common.signOut': 'Sign Out',
    'common.loading': 'Loading',
    'common.error': 'An error occurred',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.confirm': 'Confirm',

    // Common - Time Ago
    'common.timeAgo.minutes': (v) => `${v['count']}m ago`,
    'common.timeAgo.hours': (v) => `${v['count']}h ago`,
    'common.timeAgo.days': (v) => `${v['count']}d ago`,

    // Footer (legal nav + primary)
    'footer.contact': 'Contact',
    'footer.terms': 'Terms',
    'footer.privacy': 'Privacy',
    'footer.riskDisclaimer': 'Risk',
    'footer.legalNotice': 'Legal notice',
    'footer.cookies': 'Cookies',
    'footer.mica': 'MiCA',
    'footer.copyright': 'All rights reserved.',
    'footer.legal': 'Legal',

    // Errors (with interpolation)
    'errors.fetchFailed': (v) => `Failed to fetch ${v['resource']}`,
    'errors.createFailed': (v) => `Failed to create ${v['resource']}`,
    'errors.updateFailed': (v) => `Failed to update ${v['resource']}`,
    'errors.deleteFailed': (v) => `Failed to delete ${v['resource']}`,

    // Chart — demo fill tooltip (nested keys via chart.demoFills.*)
    'chart.demoFills.title': 'Demo fills',
    'chart.demoFills.side': 'Side',
    'chart.demoFills.fillPrice': 'Fill price',
    'chart.demoFills.amountBase': (v) => String(v['base'] ?? ''),
    'chart.demoFills.usd': 'USD',
    'chart.demoFills.fee': 'Fee',
    'chart.demoFills.realizedPnl': 'Realized PnL',
    'chart.demoFills.avgEntry': 'Avg entry',

    // Chart — admin model overlay panel
    'chart.modelOverlay.title': 'Model overlay',
    'chart.modelOverlay.enable': 'Enable overlay',
    'chart.modelOverlay.tier': 'Tier',
    'chart.modelOverlay.modelType': 'Model type',
    'chart.modelOverlay.version': 'Version',
    'chart.modelOverlay.uploadId': 'Upload id',
    'chart.modelOverlay.inventoryLoading': 'Loading inventory…',
    'chart.modelOverlay.emptyInventory': (v) =>
      `No overlayable models for ${String(v['symbol'] ?? '')} ${String(v['timeframe'] ?? '')}. Switch the chart to a timeframe that has trained models (often 1h / 4h / 1d).`,
    'chart.modelOverlay.advancedManual': 'Advanced (manual)',
    'chart.modelOverlay.legend': 'Green prod · amber staging · gray candidate',
    'chart.modelOverlay.loading': 'Loading…',
    'chart.modelOverlay.error': 'Failed to load overlay',
    'chart.modelOverlay.showOverlay': 'Show overlay',
    'chart.modelOverlay.hideOverlay': 'Hide overlay',
    'chart.modelOverlay.multiSelect': 'Models',
    'chart.modelOverlay.multiSelectHint': (v) =>
      `Select up to ${String(v['max'] ?? '')} models for consensus or compare.`,
    'chart.modelOverlay.displayMode': 'Display',
    'chart.modelOverlay.consensus': 'Consensus',
    'chart.modelOverlay.compare': 'Compare',
    'chart.modelOverlay.modelPicker': 'Model',
    'chart.modelOverlay.modelPickerPlaceholder': 'Select a model…',
    'admin.researchRegistry.loopHelpId': 'help Id',
    'admin.researchRegistry.loopHelpVerdict': 'help Verdict',
    'admin.researchRegistry.loopHelpIc': 'help Ic',
    'admin.researchRegistry.loopHelpIcir': 'help Icir',
    'admin.researchRegistry.loopHelpHalfLife': 'help HalfLife',
    'admin.researchRegistry.loopHelpIsOos': 'help IsOos',
    'admin.researchRegistry.loopHelpSeries': 'help Series',
    'chart.modelOverlay.emptyTier': (v) =>
      `No ${String(v['tier'] ?? '')} models for this symbol yet.`,
    'chart.modelOverlay.inventoryError':
      'Could not load the model inventory. This is a load failure, not an empty catalogue.',

    // Chart — inv-vol LO research badge
    'chart.invVolLoTitle': 'Inv-vol LO',
    'chart.invVolLoResearch': 'Research',
    'chart.invVolLoResearchTooltip': 'Inverse-volatility long-only book — display-only research.',
    'chart.invVolLoLoading': 'Inv-vol LO…',
    'chart.invVolLoUnavailable': 'Inv-vol LO unavailable',
    'chart.invVolLoStanceLong': 'Long',
    'chart.invVolLoStanceFlat': 'Flat',
    'chart.invVolLoLongOnly': 'long-only',
    'chart.invVolLoWeight': 'wt',
    'chart.invVolLoTilt': 'vs EW',
    'chart.invVolLoRv': 'RV',
    'chart.invVolLoRank': 'rank',
    'chart.invVolLoSource': 'Source',
    'chart.invVolLoTimeframeNote': 'Book TF',
    'chart.indicatorPreferences.showInvVolLo': 'Inv-vol long-only (research)',
    'chart.indicatorPreferences.showInvVolSo': 'Inv-vol short-only (research)',
    'chart.invVolSoLoading': 'Inv-vol SO…',
    'chart.invVolSoUnavailable': 'Inv-vol SO unavailable',
    'chart.invVolSoTitle': 'Inv-vol SO',
    'chart.invVolSoResearch': 'Research',
    'chart.invVolSoResearchTooltip': 'tooltip',
    'chart.invVolSoStanceShort': 'Short',
    'chart.invVolSoStanceFlat': 'Flat',
    'chart.invVolSoShortOnly': 'short-only',
    'chart.invVolSoWeight': 'wt',
    'chart.invVolSoTilt': 'vs EW',
    'chart.invVolSoRv': 'RV',
    'chart.invVolSoRank': 'rank',
    'chart.invVolSoSource': 'Source',
    'chart.invVolSoTimeframeNote': 'Book TF',

    // Resources
    'resources.signals': 'signals',
    'resources.portfolio': 'portfolio',
    'resources.trades': 'trades',
    'resources.user': 'user',

    // Backtest — indicator benchmark (slice D: loading / timeout copy)
    'backtest.benchmark.runAll': 'Run All Indicators',
    'backtest.benchmark.running': 'Running Benchmark...',
    'backtest.benchmark.loadingMessage': 'Running all detector backtests on the server.',
    'backtest.benchmark.loadingIndeterminateHint':
      'Waiting for the first progress update from the server.',
    'backtest.benchmark.runningDetectorStep': (v) =>
      `Running detector ${String(v['current'])}/${String(v['total'])}: ${String(v['label'])}`,
    'backtest.benchmark.elapsedSeconds': (v) => `Elapsed: ${String(v['seconds'])}s`,
    'backtest.benchmark.requestTimeout': 'Benchmark request timed out.',
    'backtest.benchmark.dateRangeRequired': 'Specify start and end date.',
    'backtest.benchmark.configuration': 'Benchmark Configuration',
    'backtest.benchmark.failed': 'Benchmark failed',
    'backtest.benchmark.detectorsLoading': 'Loading detector list…',
    'backtest.benchmark.detectorsError': 'Could not load the detector list.',
    'backtest.benchmark.detectorsEmpty': 'No detectors returned from the server.',
    'backtest.benchmark.detectorsScopeTitle': (v) =>
      `Detectors in this run (${String(v['count'])})`,
    'backtest.benchmark.sortinoRatio': 'Sortino',
    'backtest.benchmark.informationCoefficient': 'IC',
    'backtest.benchmark.rankIc': 'Rank IC',
    'backtest.benchmark.benchmarkAlpha': 'Alpha (vs B&H)',
    'backtest.benchmark.metricInfo.sortinoRatio': 'Sortino tooltip',
    'backtest.benchmark.metricInfo.informationCoefficient': 'IC tooltip',
    'backtest.benchmark.metricInfo.rankIc': 'Rank IC tooltip',
    'backtest.benchmark.metricInfo.benchmarkAlpha': 'Alpha tooltip',

    // Backtest — in-sample honesty (community badge + detail banner)
    'backtest.inSampleHonesty.badge': 'In-sample',
    'backtest.inSampleHonesty.title': 'In-sample backtest (allow_in_sample)',
    'backtest.inSampleHonesty.bodyDefault':
      'This run intentionally includes bars that overlap the model training fetch / held-out eval split. Metrics are not honest forward tests.',
    'backtest.inSampleHonesty.modelEvalWindow': (v) =>
      `Model eval split (metadata): ${String(v['start'])} → ${String(v['end'])}`,
    'backtest.inSampleHonesty.backtestWindow': (v) =>
      `Backtest window: ${String(v['start'])} → ${String(v['end'])}`,
    'backtest.inSampleHonesty.tipNonPredictive':
      'Treat returns as research / curve-fit inspection — not deployable edge without a true post-cutoff OOS check.',

    'backtest.leveragedCompoundOptIn.title': 'Leveraged compound DCA (advanced)',
    'backtest.leveragedCompoundOptIn.checkbox': 'I understand liquidation and ruin risk',

    // Dashboard — paper trade (futures position mode readout)
    'dashboard.trade.futuresPositionModeAria': (v) =>
      `Futures position mode from your exchange (read-only): ${String(v['mode'] ?? '')}`,
    'dashboard.trade.futuresPositionModePrefix': 'Futures mode',
    'dashboard.trade.futuresPositionModeOneWay': 'One-way',
    'dashboard.trade.futuresPositionModeHedge': 'Hedge (dual)',
    'dashboard.trade.futuresPositionModeUnknown': 'Unknown',

    // Dashboard — paper trade stats tab (global next-intl mock resolves namespace + key)
    'dashboard.trade.statsTab.sectionTitleLegBreakdown': 'Legs & exit order types',
    'dashboard.trade.statsTab.legBreakdownTradeLegsBuyCount': 'Buy legs',
    'dashboard.trade.statsTab.legBreakdownTradeLegsSellCount': 'Sell legs',
    'dashboard.trade.statsTab.legBreakdownClosedRealizedSellMarketCount': 'Closed sells (market)',
    'dashboard.trade.statsTab.legBreakdownClosedRealizedSellLimitCount': 'Closed sells (limit)',
    'dashboard.trade.statsTab.legBreakdownClosedRealizedSellOrderTypeOtherCount':
      'Closed sells (other type)',
  };

// Stable translation function factory (handles namespace)
const createMockTranslate = (namespace: string) => {
  return (key: string, values?: Record<string, string | number>): string => {
    const fullKey = `${namespace}.${key}`;
    const translation = translations[fullKey];

    if (typeof translation === 'function' && values) {
      return translation(values);
    }

    if (typeof translation === 'string') {
      return translation;
    }

    // Fallback: return the full key (allows tests to verify correct key usage)
    return fullKey;
  };
};

vi.mock('next-intl', () => ({
  useTranslations: (namespace: string) => createMockTranslate(namespace),
  useLocale: () => 'es',
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// =============================================================================
// Mock: next-intl/navigation (v4.x Navigation)
// =============================================================================

vi.mock('next-intl/navigation', () => ({
  createNavigation: () => ({
    Link: ({ children, href }: { children: React.ReactNode; href: string }) =>
      createElement('a', { href }, children),
    redirect: vi.fn(),
    usePathname: () => '/',
    useRouter: () => mockRouter,
    getPathname: vi.fn(),
  }),
}));

// =============================================================================
// Mock: next-intl/routing (v4.x Routing)
// =============================================================================

vi.mock('next-intl/routing', () => ({
  defineRouting: (config: Record<string, unknown>) => config,
}));

// =============================================================================
// Mock: @/i18n/routing (App Routing Config)
// =============================================================================

vi.mock('@/i18n/routing', () => ({
  routing: {
    locales: ['es', 'en'],
    defaultLocale: 'es',
    localePrefix: 'always',
  },
  Link: ({ children, href }: { children: React.ReactNode; href: string }) =>
    createElement('a', { href }, children),
  redirect: vi.fn(),
  usePathname: () => '/',
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  getPathname: vi.fn(),
}));

// =============================================================================
// Mock: next/font/google (no runtime in node_modules; Next compiles at build)
// =============================================================================

vi.mock('next/font/google', () => {
  const mockFont = (
    variable: string,
    className: string
  ): { variable: string; className: string } => ({
    variable,
    className,
  });

  return {
    Space_Grotesk: (opts: { variable?: string }) =>
      mockFont(opts.variable ?? '--font-space-grotesk', 'mock-font-space-grotesk'),
    DM_Mono: (opts: { variable?: string }) =>
      mockFont(opts.variable ?? '--font-dm-mono', 'mock-font-dm-mono'),
  };
});

// =============================================================================
// Mock: next/navigation (Next.js Router)
// =============================================================================

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
  forward: vi.fn(),
  refresh: vi.fn(),
};

vi.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

// Export for test access
export { mockRouter };

// =============================================================================
// Mock: next-themes (Theme Provider)
// =============================================================================

const mockTheme = {
  theme: 'light' as 'light' | 'dark',
  setTheme: vi.fn(),
  resolvedTheme: 'light' as 'light' | 'dark',
  themes: ['light', 'dark'],
  systemTheme: 'light' as 'light' | 'dark',
};

vi.mock('next-themes', () => ({
  useTheme: () => mockTheme,
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Export for test access
export { mockTheme };

// =============================================================================
// Mock: Browser APIs
// =============================================================================
// Guarded so this setup file works under both jsdom and node environments.
// Tests that don't need a DOM can opt into node via `// @vitest-environment node`
// at the top of the file (avoids ~2s of jsdom env setup per file).

if (typeof window !== 'undefined') {
  // matchMedia (for responsive design tests)
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // IntersectionObserver (for lazy loading tests)
  class MockIntersectionObserver {
    readonly root: Element | null = null;
    readonly rootMargin: string = '';
    readonly thresholds: ReadonlyArray<number> = [];

    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
    takeRecords = vi.fn().mockReturnValue([]);
  }

  Object.defineProperty(window, 'IntersectionObserver', {
    writable: true,
    value: MockIntersectionObserver,
  });

  // ResizeObserver (for responsive component tests)
  class MockResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
  }

  Object.defineProperty(window, 'ResizeObserver', {
    writable: true,
    value: MockResizeObserver,
  });

  // Pointer capture — Radix Select calls these; jsdom’s Element lacks them.
  if (typeof Element !== 'undefined') {
    const elementProto = Element.prototype as typeof Element.prototype & {
      hasPointerCapture?: (pointerId: number) => boolean;
      setPointerCapture?: (pointerId: number) => void;
      releasePointerCapture?: (pointerId: number) => void;
    };

    if (typeof elementProto.hasPointerCapture !== 'function') {
      elementProto.hasPointerCapture = (): boolean => false;
    }

    if (typeof elementProto.setPointerCapture !== 'function') {
      elementProto.setPointerCapture = (): void => {};
    }

    if (typeof elementProto.releasePointerCapture !== 'function') {
      elementProto.releasePointerCapture = (): void => {};
    }

    if (typeof elementProto.scrollIntoView !== 'function') {
      elementProto.scrollIntoView = (): void => {};
    }
  }

  // localStorage/sessionStorage safety shim:
  // Some CI/dev environments inject partial storage objects (or invalid
  // --localstorage-file wiring), which breaks many behavior tests.
  function createStorageShim(): Storage {
    const store = new Map<string, string>();

    return {
      get length() {
        return store.size;
      },
      clear() {
        store.clear();
      },
      getItem(key: string): string | null {
        return store.has(key) ? (store.get(key) ?? null) : null;
      },
      key(index: number): string | null {
        return Array.from(store.keys())[index] ?? null;
      },
      removeItem(key: string): void {
        store.delete(key);
      },
      setItem(key: string, value: string): void {
        store.set(key, String(value));
      },
    };
  }

  function ensureStorageApis(): void {
    const local = window.localStorage as Storage | undefined;

    if (
      !local ||
      typeof local.getItem !== 'function' ||
      typeof local.setItem !== 'function' ||
      typeof local.removeItem !== 'function' ||
      typeof local.clear !== 'function'
    ) {
      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        writable: true,
        value: createStorageShim(),
      });
    }

    const session = window.sessionStorage as Storage | undefined;

    if (
      !session ||
      typeof session.getItem !== 'function' ||
      typeof session.setItem !== 'function' ||
      typeof session.removeItem !== 'function' ||
      typeof session.clear !== 'function'
    ) {
      Object.defineProperty(window, 'sessionStorage', {
        configurable: true,
        writable: true,
        value: createStorageShim(),
      });
    }
  }

  ensureStorageApis();
}

// =============================================================================
// Test Environment Info (useful for debugging)
// =============================================================================

if (process.env['VITEST_VERBOSE']) {
  console.info('🧪 Test Environment Setup');
  console.info('  NODE_ENV:', process.env['NODE_ENV'] ?? 'undefined');
}
