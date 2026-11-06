# A push to master IS a production deploy (MANDATORY)

Owner, 2026-09-02: _"everything you push to master is auto deployed on railways prod -.- (harden
your memory and hooks -.-)"_ — after I wrote that "prod has not redeployed" and reasoned from it.

## The rule

`git push origin master` deploys to Railway production. There is **no** separate promote step,
**no** staging environment, and **no** manual gate between the push and live user traffic.

So "committed" and "deployed" are the same event. Two habits are therefore banned:

1. **Never explain a prod/local difference with "prod has not picked it up yet."** It has. If prod
   and localhost disagree, the cause is something else — and the candidates are known:
   - **different DATABASES.** Localhost has its own `pulsai` DB, typically thin backfilled rows.
     Measured 2026-09-02: local `BTC/USDT 1d` v2 held **5 rows ever**, all `BUY 1.0000`, while prod
     held a live varied stream (`BUY .5557 / SELL .7212 / HOLD .3201 / SELL 1.0 / SELL .8007`).
     Comparing a Telegram alert (prod) against a chart (localhost) compares two stores.
   - **different model artifacts** — prod loads from R2, localhost from `apps/api/models/`.
   - **env vars are per Railway SERVICE** (`check-the-flag-on-the-service-that-runs-it`).
2. **Never reason about "what the deploy will do later."** Ask what the change does to LIVE users
   now. A behaviour change in a worker, a gate, a monitor or an endpoint is live within minutes.

## Why this is worth a rule

The failure is not laziness — it is a wrong mental model that produces confident, wrong analysis.
Believing prod lagged, I built a train/serve-skew hypothesis: prod feeding a constant
`smoothed_rsi` while localhost fed the repaired series after `0ff1520a9`. Prod already had the fix.

The hypothesis was **also** refuted on its own merits, and that part is worth keeping: the deployed
1d `gradient_boosting_clf` v2 lists `smoothed_rsi` in its 162 `feature_columns`, but its
`feature_importances_` for that column is **exactly `0.0`** (128 of 162 features are nonzero). A
feature that was constant during training is never split on, so repairing it cannot move that
model's predictions. Two independent errors, one of which the measurement caught.

## What actually protects prod

The verify gates are the ONLY thing between a commit and users:

- `cd apps/api && ./scripts/verify.sh`
- `cd apps/web && pnpm verify`

That is why they are not optional, why `--no-verify` is banned
(`.claude/hooks/no_verify_push_guard.py`), and why a red gate is never "pre-existing, push anyway"
(`.claude/rules/own-the-defect-not-the-blame.md`).

Before pushing, state in one line what the change does to live users. If that sentence is
uncomfortable, the push is not ready.

Companion memory: `push-to-master-deploys-prod`. Related:
`.claude/rules/no-heavy-work-in-the-serving-container.md` (the other way prod gets hurt from here).
