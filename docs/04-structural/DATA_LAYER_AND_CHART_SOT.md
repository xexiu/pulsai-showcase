# Data layer and chart SoT (frontend)

**Last updated:** 2026-05-21

This document is the structural source of truth for how the PulsAI web app loads, caches, and prefetches market/chart/trading data with **TanStack Query**. It complements [CODING_STANDARDS.md](./CODING_STANDARDS.md) §5.4.

---

## Principles

1. **TanStack Query is the server-state cache** — `useQuery` / `useMutation` only; fetchers in `@/config/queryFetchers*`, keys in `@/config/queryKeys*`, query option builders in `@/lib/query-options/`.
2. **Prefetch uses the same query options as hooks** — `queryClient.prefetchQuery` must share `queryKey`, `queryFn`, and `staleTime` with the hook that owns the data.
3. **Policy modules decide behavior** — not inline magic numbers in components.
4. **Prefetch is bounded** — concurrency cap + stagger delay reduce burst load on slow networks.

---

## Where each layer lives (single SoT per concern)

| Concern                                                                           | Location                                                             | Examples                                                                                                                                                        |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Query keys                                                                        | `@/config/queryKeys*` (sharded by domain; barrel in `queryKeys.ts`)  | `tradingPortfolioKeys`, `liveExchangeBalanceFetchKeys`, `chartIndicatorsKeys`                                                                                   |
| Query fetchers                                                                    | `@/config/queryFetchers*`                                            | `fetchOhlcv`, `fetchChartIndicators`                                                                                                                            |
| `useQuery` option builders (shared between hooks and prefetch runners)            | `@/lib/query-options/`                                               | `buildOhlcvDataUseQueryOptions`, `buildChartIndicatorsDataUseQueryOptions`                                                                                      |
| Bootstrap prefetch option builders                                                | `@/utils/dashboard-bootstrap-prefetch/`                              | `buildBacktestProductionModelsUseQueryOptions`, `buildModelsListUseQueryOptions`, `buildExchangeConnectionsUseQueryOptions`, `buildTradingModesUseQueryOptions` |
| Per-consumer caching policy (`staleTime`, polling, instantSwap, peer-TF prefetch) | `@/config/chart-data-policy/`                                        | `chartDataPolicy.defaults.ts`, `resolveChartPrefetchExecution`                                                                                                  |
| Concurrency / stagger / idle-defer defaults                                       | `@/config/query-prefetch/`, `@/config/dashboard-bootstrap-prefetch/` | `queryPrefetch.defaults.ts`, `dashboardBootstrapPrefetch.defaults.ts`                                                                                           |

Inline `queryKey: ['...']` arrays inside hooks are forbidden — go through a factory in `@/config/queryKeys*`. New query option builders MUST land in `@/lib/query-options/` so the hook and the prefetch runner share one source. Bootstrap-only builders live in `@/utils/dashboard-bootstrap-prefetch/`.

---

## Policy modules

| Module                            | Path                                                | Controls                                                                                                        |
| --------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Chart Data Policy                 | `apps/web/src/config/chart-data-policy/`            | Per chart consumer: `staleTime`, polling, `instantSwap`, `prefetchPeerTimeframes`, prefetch concurrency/stagger |
| Dashboard bootstrap prefetch      | `apps/web/src/config/dashboard-bootstrap-prefetch/` | Layout mount: trading modes, connections, backtest models; nav-intent models; idle defer + concurrency          |
| Query prefetch execution defaults | `apps/web/src/config/query-prefetch/`               | Global defaults: max concurrent (2), stagger (100ms), idle timeout (500ms)                                      |

Flip flags in `chartDataPolicy.flags.ts` or `dashboardBootstrapPrefetch.defaults.ts` to change behavior app-wide for that surface.

### Live WebSocket vs REST poll (do not conflate)

| Surface              | Forming candle (live OHLC)         | REST `staleTime` | REST interval poll (`refetchInterval`)         |
| -------------------- | ---------------------------------- | ---------------- | ---------------------------------------------- |
| Dashboard embedded   | Binance WS via `useLiveChartReady` | 60s              | 60s                                            |
| Paper trade embedded | Same WS stack                      | 15s              | 10s                                            |
| Full chart           | Same WS stack                      | 60s              | **none** — bar-close / TF / pref triggers only |

**`pollIntervalMs: false` on full** avoids timer hits on the heaviest `chart-indicators` payload (429 guard); it does **not** disable WS.

Embedded surfaces: `useEmbeddedDashboardChartDisplayData` + `useEmbeddedDashboardChartChrome` + `config/embedded-dashboard-chart.ts` (surface → consumer).

---

## Chart peer-timeframe prefetch

**Goal:** When the user opens a chart page, warm cache for all other allowed timeframes so TF clicks are fast.

**Flow:**

```
Page mount → useChartPeerTimeframePrefetch (once per symbol + TF set)
          → prefetchOhlcvPeerTimeframes | prefetchChartIndicatorsPeerTimeframes
          → prefetchQueryClientTasks (concurrency + stagger)
          → queryClient.prefetchQuery (same options as useOHLCVData / useChartIndicatorsData)
```

**Consumers with `prefetchPeerTimeframes: true`:** `dashboard`, `trade`, `full`.

**Consumers with `prefetchPeerTimeframes: false`:** `signals` (2-candle probe), `backtest` (static run).

**TF click:** Does **not** re-run peer prefetch (effect omits `activeTimeframe`). Active TF is loaded by `useChartIndicatorsData` (dashboard, trade, full) or `useOHLCVData` (signals, backtest); TanStack dedupes in-flight prefetch for the same key.

**Wiring:**

| Surface                 | Hook                                                                                                        |
| ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| Dashboard + paper trade | `useEmbeddedDashboardChartPeerTimeframePrefetch` (`chart-indicators`; dashboard excludes tier-disabled TFs) |
| Full chart              | `useFullChartPeerTimeframePrefetch` in `FullChartContent.tsx`                                               |

**Nav intent (hover/focus before navigation):**

| Surface      | Hook / util                                                                                                                                                                                                       |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dashboard    | `useDashboardFullChartNavIntentPrefetch` → `prefetchFullChartNavIntentChartIndicators` (active TF only, user prefs CSV) on the embedded chart “advanced chart” link via `useTradingChartFullChartLinkIntentProps` |
| Backtest nav | `useDashboardBacktestModelsNavIntentPrefetch` → `prefetchDashboardBacktestModels` (existing)                                                                                                                      |

Policy flag: `CHART_DATA_POLICY.dashboard.prefetchFullChartOnNavIntent` (default `true`). Only the active timeframe is warmed on intent — peer TFs remain mount-scoped to avoid 429 bursts.

---

## Chart timeframe swap loading (TF click UX)

**SoT module:** `apps/web/src/lib/chart-timeframe-swap/` — detection, i18n copy, hooks.

| Piece                               | Location                                          | Role                                                                       |
| ----------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------- |
| `resolveChartTimeframeSwapInFlight` | `lib/chart-timeframe-swap/`                       | Payload TF ≠ selected TF                                                   |
| `useChartTimeframeSwapUi`           | `lib/chart-timeframe-swap/`                       | `{ isActive, overlayMessage }` for any surface                             |
| `ChartTimeframeSwapOverlay`         | `components/molecules/ChartTimeframeSwapOverlay/` | Dim overlay UI (`chart.loadingNewTimeframe`)                               |
| `ChartTimeframeSwapOverlaySlot`     | same                                              | Wrap embedded charts — pass `selectedTimeframe` + `responseTimeframe` only |
| Initial load (no candles yet)       | `ChartLoadingState` via `ChartContainer`          | `loading.chartWithSymbol` — not TF-swap overlay                            |

**Wiring (pass `responseTimeframe` from chart-indicators, not pre-translated strings):**

| Surface       | Integration                                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| Dashboard     | `TechnicalAnalysisSection` → `DashboardChartShell` → `DashboardChartFrame` + `ChartTimeframeSwapOverlaySlot` |
| Paper trade   | `TradeChartPanel` → same shell/frame path                                                                    |
| Full chart    | `FullChartViewport` calls `useChartTimeframeSwapUi`; `FullChartViewportChartPane` renders overlay            |
| Future charts | Reuse `ChartTimeframeSwapOverlaySlot` or `useChartTimeframeSwapUi` + `ChartTimeframeSwapOverlay`             |

Prefetch cache hits still show loading briefly (`CHART_TIMEFRAME_SWAP_MIN_FEEDBACK_MS`) so TF clicks always give feedback.

**Utils:** `apps/web/src/utils/chart-timeframe-prefetch/`

**Query builders:**

- `buildOhlcvDataUseQueryOptions` — `apps/web/src/hooks/useOHLCVData/`
- `buildChartIndicatorsDataUseQueryOptions` — `apps/web/src/hooks/useChartIndicatorsData/`
- `useDashboardChartDisplayData` — dashboard/trade embedded chart (`chart-indicators` + `buildChartLayersFromIndicatorsResponse`)

---

## Dashboard bootstrap prefetch

**Goal:** Warm shared trading shell + backtest models when the dashboard layout mounts.

**Flow:**

```
dashboard/layout.tsx → DashboardLayoutPrefetch
                    → useDashboardTradingBootstrapPrefetch (modes + connections)
                    → useDashboardBacktestModelsPrefetch (production models, default symbol/TF)
```

**Nav intent:** Hover/focus on backtest top-bar link → `useDashboardBacktestModelsNavIntentPrefetch` via `useDashboardNavLinkIntentProps`.

**Query builders (shared with hooks):**

- `buildTradingModesUseQueryOptions`
- `buildExchangeConnectionsUseQueryOptions`
- `buildBacktestProductionModelsUseQueryOptions`
- `buildModelsListUseQueryOptions` (admin `useModels` / `fetchModelsList`)

**Reused by:** `useDashboardTopBarModel`, `usePaperTradePageModel`, `useExchangeConnectionsListQuery`, `performance-review/page.tsx`, `useModels` (scope `backtest`).

**Utils:** `apps/web/src/utils/dashboard-bootstrap-prefetch/`

---

## Prefetch execution (concurrency + stagger + idle)

| Setting                  | Default | Domain                   | Meaning                                                  |
| ------------------------ | ------- | ------------------------ | -------------------------------------------------------- |
| `prefetchMaxConcurrent`  | `2`     | chart + dashboard        | At most N prefetches in flight                           |
| `prefetchStaggerDelayMs` | `100`   | chart + dashboard        | Delay before a worker starts its next task               |
| `prefetchDeferUntilIdle` | `true`  | dashboard bootstrap only | Run layout bootstrap prefetches in `requestIdleCallback` |
| `prefetchIdleTimeoutMs`  | `500`   | dashboard bootstrap      | Max wait before idle-deferred work runs anyway           |

**Implementation:**

- `runPrefetchTasksWithConcurrency` — `apps/web/src/utils/query-prefetch/`
- `prefetchQueryClientTasks` — wraps `queryClient.prefetchQuery` tasks
- `schedulePrefetchWhenIdle` — browser idle scheduling (Safari: `requestAnimationFrame` fallback)
- `runDashboardBootstrapPrefetchTask` — applies idle policy in dashboard prefetch hooks

Resolved per domain via:

- `resolveChartPrefetchExecution(consumer)` — concurrency + stagger
- `resolveDashboardBootstrapPrefetchExecution()` — concurrency + stagger for bootstrap runners
- `resolveDashboardBootstrapPrefetchSchedule()` — idle defer for layout hooks

---

## What we do not prefetch

- `useAppConfig` / `useTradingConfig` (already loaded globally; long `staleTime`)
- Admin health, training jobs, audit logs
- Settings hub pages (load on sub-route)
- Bulk admin model lists

---

## Adding a new prefetch slice

1. Add policy flag(s) to the appropriate SoT module.
2. Extract or reuse `build*UseQueryOptions` matching the hook.
3. Add `prefetch*` runner calling `prefetchQueryClientTasks`.
4. Add a thin `use*Prefetch` hook (mount-scoped; avoid re-running on UI toggles).
5. Behavior tests: policy invariants, runner guards, hook calls runner once.

---

## Related docs

- [CODING_STANDARDS.md](./CODING_STANDARDS.md) §5.4 — TanStack Query rules
- [CHART_TIME_DISPLAY_SOT.md](./CHART_TIME_DISPLAY_SOT.md) — candle time / timezone
- [FE_CONFIG_DESIGN.md](../02-technical/FE_CONFIG_DESIGN.md) — public config
