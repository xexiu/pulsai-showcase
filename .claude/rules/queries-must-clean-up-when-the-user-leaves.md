# A query must clean up when the user leaves (MANDATORY)

Owner, 2026-09-03, on the liquidation-map poll: _"is this corectly unmoneuted? and aborted if
conenction lost or user clicks another tab/tiemfreme/any other things that makes him go way?"_

The right question, and the answer is not the reassuring one. Most of the cleanup IS automatic.
Exactly one part is not, and it is invisible.

## What TanStack does for you, verified in `@tanstack/query-core` 5.100.10

| the user…                           | what happens                                                                 | where                                                                |
| ----------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| navigates away / component unmounts | the poll timer is cleared                                                    | `queryObserver.js` `onUnsubscribe → destroy → #clearRefetchInterval` |
| switches timeframe or symbol        | the queryKey changes, the old query loses its observer, gc scheduled         | `query.js` `removeObserver`                                          |
| switches browser tab                | ticks still fire but SKIP fetching when `refetchIntervalInBackground: false` | `queryObserver.js` line 215                                          |
| loses connection                    | nothing is attempted; it resumes on reconnect                                | `retryer.js` — default `networkMode: 'online'`                       |
| turns the feature off               | with `enabled: false` the interval is never scheduled                        | `queryObserver.js` line 211                                          |

## The part that is NOT automatic

**An in-flight request is aborted only if the `queryFn` consumed the `signal`.**

```js
// query.js removeObserver, when the last observer goes
if (this.#abortSignalConsumed || this.#isInitialPausedFetch()) {
  this.#retryer.cancel({ revert: true }); // request ABORTED
} else {
  this.#retryer.cancelRetry(); // request RUNS TO COMPLETION
}
```

So `queryFn: () => fetchThing(x)` and `queryFn: ({ signal }) => fetchThing(x, signal)` differ by one
destructured parameter, and that parameter is the difference between a cancelled request and a
leaked one. There is no type error, no lint error and no failing test either way — the flag is set
by the mere ACT of reading `signal`, so nothing static can infer it from the outside.

On a polling query this compounds: it leaks once per tick, not once per visit.

## The rule

1. Every `queryFn` that performs I/O takes `{ signal }` and forwards it to the fetcher.
2. A query that declares `refetchInterval` must do so — no exceptions that are not allowlisted.
3. Do not hand-roll `AbortController` in a hook to get this. The context signal already exists and
   is wired to the cache lifecycle; a second controller just adds a thing to forget to abort.

## Enforcement — executable, not this file

`apps/web/tests/unit/architecture/polling-queries-abort-on-unmount.test.ts`, in `pnpm test`.

It is a **ratchet**, not a cleanup mandate. Measured when written: 18 files declare
`refetchInterval`, 4 never consume the signal — all four live-exchange queries, which talk to an
exchange SDK client rather than the app fetch wrapper and may have no abort surface to forward to.
Those are allowlisted **with that reason**; the gate blocks a fifth. It also fails when an
allowlisted file is FIXED, so the exemption list cannot rot into a list of problems nobody has.

Two of its four assertions exist only to stop it passing vacuously — one fails if the scan finds no
files, one if `refetchInterval` stops being the spelling. A gate that quietly matches nothing is
worse than no gate, because it reports green.

Read the numbers from the test, not from here: this file is prose and prose drifts
(`.claude/rules/verify-and-judge-not-quote.md`). The test is the claim that gets checked.

## The sibling failure this rule does not cover

Cleanup is about stopping work. Staleness is about restarting it. A query with
`refetchIntervalInBackground: false` also needs `refetchOnWindowFocus` when the app-wide default
disables it (`apps/web/src/config/react-query.ts`) — otherwise a returning user waits a full
interval staring at data from before they left. Skipped ticks are skipped, never deferred.
