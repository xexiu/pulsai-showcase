# ADR-017: Challenges Hub & Trading Arena (Paper-First)

## Status

**ACCEPTED (Strategic architecture — implementation phased)** — 2026-04-17

## Date

2026-04-17

## Authors

Architecture (main) — aligns product “challenge hub” / “AI Trading Arena” with existing trading boundaries, notifications, and compliance posture.

## Context

### Business drivers

1. **Phase 3+ community** (`docs/03-functional/FEATURES.md`): “Community Features” is planned post-core trading value.
2. **Roadmap vision** (`docs/01-business/ROADMAP.md` §5.1): “AI Trading Arena” — leaderboards, follow/copy **ideas**, community voting; reference competitor <https://nof1.ai/>.
3. **Differentiation**: Crypto-first, ensemble ML + TA signals already in pipeline; hub should **surface** strategy transparency (model version, indicators, risk framing) rather than opaque leaderboards only.

### Technical reality (must not regress)

1. **`docs/04-structural/TRADING_DOMAIN_BOUNDARIES.md`**: Strategy/signals own **intent**; execution owns **modes and adapters**; `trading_automations` holds **strategy snapshot JSON + execution policy** — automation row is **policy SoT**, not a second order engine. Orders still flow through **`UnifiedTradingService.place_order`** (and documented paper/demo paths).
2. **`docs/08-adr/ADR-009-auto-trading-strategy.md`**: Full auto-trading with user funds is **deferred** with strict phased safeguards. The Challenges Hub must default to **informational + paper-attested** narratives unless/until product and legal explicitly approve execution tie-ins.
3. **`docs/03-functional/TELEGRAM_ACCOUNT_LINKING.md`**: Automated Telegram pushes for signals/confluences require **linked `user_id`** and **subscription tier** rules (e.g. Starter+). Challenge alerts are a **new notification topic** and must reuse or deliberately extend this policy (no silent bypass).
4. **`docs/01-business/REGULATION_ROADMAP.md`**: MiCA/CNMV posture — signal provider / informational tools; **disclaimers**, no guaranteed returns in marketing, **Kelly** and similar displays already carry legal sensitivity — same discipline applies to challenge titles and performance claims.

### Problem statement

Without an ADR, “challenges” risk being implemented as:

- A duplicate execution engine, or
- A social feed that implies **personalized investment advice**, or
- Unlabeled **synthetic** personas indistinguishable from humans, or
- Telegram spam that **circumvents** tier and consent rules.

This ADR fixes the **bounded context**, **data ownership**, **phasing**, and **compliance hooks** so engineering can ship vertical slices safely.

## Decision

### 1. Naming and scope (canonical product language)

| Term              | Meaning                                                                                                    |
| ----------------- | ---------------------------------------------------------------------------------------------------------- |
| **Challenge**     | A **time-bounded or ongoing public showcase** of a trading **thesis** with rules, metrics, and audit tier. |
| **Participant**   | The **creator** of the challenge: human user or **platform-managed synthetic agent** (ML/LLM/bot persona). |
| **Subscription**  | User opts in to **updates** for a challenge (feed + optional Telegram). Distinct from **social follow**.   |
| **Trading Arena** | Product marketing name for the **hub** listing challenges + leaderboards + detail views.                   |

**UI copy**: Prefer “**Arena**” / “**Challenges**” over “competition with prizes” until legal approves any real-money or token-linked mechanics (see ROADMAP §5.4 token — **out of scope** for this ADR).

### 2. Bounded context (DDD-level)

Introduce a dedicated application/domain area: **`challenges`** (or `trading_arena` package name — **implementers choose one** and document in `PROJECT_STRUCTURE.md` when first slice lands).

**Owns:**

- Challenge CRUD (metadata, rules, visibility, status).
- Leaderboard / ranking **materialized views or scheduled aggregation** (not hot-path on every HTTP request at scale).
- User **subscriptions** to challenge events.
- Optional **social follow** of creator (separate use case; may delegate to future `social` / `profiles` module).
- **Synthetic participant** registry (persona id, disclosure text, model links).

**Does not own:**

- Exchange order placement (delegates to existing **trading** application services).
- ML training/inference (consumes **signals** / **automations** / **backtest** artifacts by reference).
- Billing (Stripe) except **feature flags by tier** via existing auth/subscription dependencies.

### 3. Core invariant: one execution path

Any “challenge” that results in trades must **reference**:

- `trading_automations` row(s) and/or **paper portfolio** events already defined in `TRADING_DOMAIN_BOUNDARIES.md`, and
- **`UnifiedTradingService.place_order`** (or documented demo/paper helpers) — **no parallel executor**.

The hub **displays** and **notifies**; execution remains **explicit user action** unless ADR-009 phases and legal gates allow otherwise.

### 4. Participant types and disclosure

| Type                       | Requirements                                                                                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Human creator**          | Linked `user_id`; public profile optional; abuse/report path.                                                                                      |
| **Synthetic / AI persona** | Immutable **`participant_kind = synthetic`**; display name + **“Simulated / Not a human”** badge; link to model or policy version when applicable. |

**Forbidden**: Presenting synthetic results as **verified live** PnL without the same audit pipeline as human-attested challenges.

### 5. Verification tiers (trust model)

Implementers **must** persist an explicit **`attestation_tier`** (names indicative):

| Tier            | Meaning                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `IDEA_ONLY`     | Narrative + levels only; **no** linked paper fills; educational.                                                          |
| `PAPER_LINKED`  | Equity curve / fills sourced from **internal paper** events tied to audit tables (append-only preferred).                 |
| `LIVE_ATTESTED` | **Future / legal-gated**: requires documented consent, exchange read proofs, and support burden — **not** MVP for hub v1. |

Leaderboards default to sorting with **tier visibility** and **risk-adjusted metrics** (Sharpe, max drawdown, win rate) — not **ROI alone**.

### 6. Challenge lifecycle (state machine)

Suggested states (exact enum in code when implemented):

```
DRAFT → PUBLISHED → PAUSED → ENDED | ARCHIVED
```

- **`PUBLISHED`**: visible on hub; events may fire.
- **`PAUSED`**: visible but frozen metrics; no new subscriber alerts (or single “paused” digest).
- **`ENDED`**: immutable snapshot for historical leaderboard.
- **`ARCHIVED`**: hidden from default hub; deep-link retained for compliance/audit.

### 7. Data model (logical — physical migration when slice ships)

**Challenge** (aggregate root sketch):

- `id`, `creator_user_id` (nullable only if **platform** owns synthetic row), `participant_kind`, `synthetic_persona_id` (nullable)
- `title`, `description`, `symbol`, `timeframe`, `visibility` (`public` | `unlisted` | `private_to_subscribers`)
- `rules_json` (max leverage cap **display**, position sizing philosophy, allowed modes paper/demo only for v1)
- `attestation_tier`, `starts_at`, `ends_at` (nullable for ongoing)
- `strategy_ref` — FK or JSON pointer: `{ "trading_automation_id": "uuid" }` and/or `{ "signal_policy_id": "..." }` — **references only**, not embedded execution
- `created_at`, `updated_at`, `version` (optimistic concurrency for updates)

**ChallengeSubscription**:

- `user_id`, `challenge_id`, `notify_email`, `notify_telegram`, `notify_in_app`, `created_at`
- Unique `(user_id, challenge_id)`

**ChallengeEvent** (append-only audit + fan-out source):

- `challenge_id`, `event_type` (e.g. `CHALLENGE_PUBLISHED`, `THEsis_UPDATE`, `PAPER_FILL`, `CHALLENGE_ENDED`), `payload_json`, `occurred_at`
- Consumers: WebSocket fan-out, Telegram worker, email digest (future)

**LeaderboardSnapshot** (optional for scale):

- Periodic job writes denormalized metrics per `challenge_id` + window.

### 8. API shape (future contract — not implemented by this ADR)

Prefix suggestion: **`/api/v1/challenges`** (user-scoped) and **`/api/v1/admin/challenges`** (moderation) if needed.

| Method   | Path                              | Purpose                                    |
| -------- | --------------------------------- | ------------------------------------------ |
| `GET`    | `/challenges`                     | Paginated hub list (filters, tier, symbol) |
| `POST`   | `/challenges`                     | Create (human; role + tier gated)          |
| `GET`    | `/challenges/{id}`                | Detail + strategy refs + disclaimers       |
| `POST`   | `/challenges/{id}/subscribe`      | Subscribe to updates                       |
| `DELETE` | `/challenges/{id}/subscribe`      | Unsubscribe                                |
| `POST`   | `/challenges/{id}/follow-creator` | Optional; distinct from subscribe          |

**Authorization**: Reuse JWT; **rate limits** on create and subscribe; **admin** endpoints for synthetic seeding and abuse takedown.

### 9. Telegram integration

- New notification channel: **`challenge_event`** (or subtypes in payload).
- **Must** respect: linked Telegram + **tier** policy documented in `TELEGRAM_ACCOUNT_LINKING.md` unless product explicitly documents a **free-tier digest** (legal + PM decision — default **same tier as signal pushes**).
- Implement **quiet hours** and **per-user daily cap** to prevent hub from becoming spam vector (see `USER_STORIES` notification prefs).

### 10. Frontend (apps/web)

- Routes under authenticated dashboard, e.g. **`/dashboard/arena`**, **`/dashboard/arena/[challengeId]`** (exact paths in FE task).
- Reuse design language from **`docs/03-functional/UI_UX_REQUIREMENTS.md`** (SignalCard patterns: entry / targets / stop / R:R where applicable).
- **Disclaimers**: Every detail view renders shared **`SignalDisclaimer`**-class component or arena-specific legal shard (i18n per `I18N_LEGAL.md` patterns).

### 11. Phased delivery (vertical slices for roadmap)

| Phase | Goal                                                                                              | Outcome                                                               |
| ----- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **A** | Read-only hub + detail from **seeded** challenges                                                 | FE + BE list/detail; no TG                                            |
| **B** | Human-created challenges **IDEA_ONLY** + subscriptions (in-app only)                              | CRUD minimal; audit `ChallengeEvent`                                  |
| **C** | **PAPER_LINKED** — bind challenge to `trading_automation_id` + paper fill events; leaderboard job | Provable paper equity; metrics                                        |
| **D** | Telegram + email digests; **follow creator** optional                                             | Policy tables + worker fan-out                                        |
| **E** | Synthetic personas + voting / social (if still desired)                                           | Moderation tools; ADR amendment if voting implicates governance/token |

**Stop line**: Phase **C** is the first **credible** “Arena” for retail trust. Phases **D–E** are engagement multipliers.

### 12. Non-goals (explicit)

- **Custody** or pooled funds.
- **Real-money betting** on challenge outcomes (token or fiat) — see ROADMAP §5.4; separate legal ADR if ever revived.
- **Guaranteed return** copy in challenge titles or hub badges.
- **Bypass** of ADR-009 safeguards for any auto-execution narrative tied to challenges.

### 13. Security & abuse

- Rate limit: challenge create, subscribe, comment (if comments exist).
- Report/takedown workflow for **human** creators; synthetic challenges only creatable by **`super_admin`** or controlled worker role.
- **No PII** in public `rules_json`; API keys never in payloads.
- CSRF-safe mutations; idempotency on subscribe where applicable.

### 14. Testing & observability

- Contract tests for hub API; property tests for state transitions.
- Load test leaderboard aggregation separately from OLTP.
- Metrics: `challenge_subscribe_total`, `challenge_telegram_send_errors`, `arena_list_latency_p95`.

## Consequences

### Positive

- Clear **separation** between social/educational hub and **execution**, preserving `TRADING_DOMAIN_BOUNDARIES.md`.
- Engineers can **parallelize** FE hub vs BE aggregates vs Telegram worker with stable contracts.
- Compliance hooks (tier, disclosure, disclaimers) are **first-class**, not bolt-on.

### Negative

- **Extra tables** and Celery/beat jobs for snapshots and TG fan-out — operational cost.
- **Product complexity**: users may confuse “subscribe to challenge” vs “copy trade”; UX must keep distinction obvious.

## Alternatives considered

1. **Implement hub as only TradingView-style social feed** — Rejected as primary: misses ML transparency and PulsAI automation linkage.
2. **Allow challenges to host arbitrary webhook execution** — Rejected: security and regulatory surface explode.
3. **Blockchain-verified performance** — Deferred indefinitely; not required for v1 trust (internal paper audit is enough).

## Related documentation

- `docs/04-structural/TRADING_DOMAIN_BOUNDARIES.md`
- `docs/08-adr/ADR-009-auto-trading-strategy.md`
- `docs/03-functional/TELEGRAM_ACCOUNT_LINKING.md`
- `docs/02-technical/LIVE_SIGNAL_FLOW.md`
- `docs/01-business/REGULATION_ROADMAP.md`
- `docs/03-functional/FEATURES.md` (Phase 3 community)
- `docs/01-business/ROADMAP.md` — **Sprint 5.1** (implementation checklist)

## Amendment process

Changes to **attestation tiers**, **Telegram tier policy**, or **execution coupling** require:

1. Update this ADR (revision date in header).
2. Update `TRADING_DOMAIN_BOUNDARIES.md` if execution touchpoints move.
3. Legal review tick-box in `REGULATION_ROADMAP.md` when moving from `PAPER_LINKED` toward **`LIVE_ATTESTED`** or any auto-follow execution.

---

## Changelog

| Date       | Change                                      |
| ---------- | ------------------------------------------- |
| 2026-04-17 | Initial acceptance — strategic architecture |
