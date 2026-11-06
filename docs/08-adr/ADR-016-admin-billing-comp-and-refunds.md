# ADR-016: Admin billing — comp, refunds, and Stripe alignment

## Status

**ACCEPTED** (2026-03-21)

## Context

PulsAI uses Stripe for subscription payments. Support sometimes needs to:

- **Comp** (grant entitlement without a matching Stripe charge)
- **Refund** a charge without opening Stripe Dashboard for every case
- See whether **database `subscription_tier`** matches **Stripe subscription price** (drift)

Customer **cancel** and self-serve plan changes remain **Stripe Customer Portal** (existing user billing settings).

## Decision

### Roles

- **Billing snapshot, refund, sync-tier** API routes: **`super_admin` only** (same bar as subscription tier `PATCH` on users).

### Modes of tier change

| Mode                    | Mechanism                                                 | Stripe                                                                 |
| ----------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------- |
| **DB comp**             | `PATCH /api/v1/admin/users/{id}` with `subscription_tier` | Not updated; support may align Stripe separately if billing must match |
| **Stripe-aligned tier** | `POST /api/v1/admin/users/{id}/billing/sync-tier`         | Updates subscription item price; webhooks reconcile DB                 |

### Refunds

- Implemented via **Stripe Refund API** on an **invoice** owned by the user’s Stripe customer.
- **Audit**: Every successful refund is logged (`log_admin_action` with action name `stripe_refund`).

### Cancel

- No change: users use **Portal** from `/dashboard/settings/billing`.

## Consequences

### Positive

- Clear product rules; less accidental drift narrative in docs
- Refunds and snapshots are auditable

### Negative

- `sync-tier` can prorate charges; ops must understand `proration_behavior`
- DB-only comp can still diverge from Stripe until manually fixed

## Related

- [`apps/api/src/api/admin/billing_routes.py`](../../apps/api/src/api/admin/billing_routes.py)
- [`docs/02-technical/ADMIN_USER_LIFECYCLE.md`](../02-technical/ADMIN_USER_LIFECYCLE.md)
