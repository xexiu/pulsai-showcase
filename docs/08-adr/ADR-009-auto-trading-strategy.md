# ADR-009: Auto-Trading Strategy

## Status

**ACCEPTED** - 2026-01-29

## Context

During Sprint 1.6 planning, the question arose: Should we add an "auto-pilot" toggle that automatically executes buy/sell signals when users have their exchange API connected?

### The Question

```
User has exchange API connected → ML generates BUY signal → Should we auto-execute the trade?
```

### Risk Analysis

| Risk Type            | Severity | Description                                                 |
| -------------------- | -------- | ----------------------------------------------------------- |
| **Legal/Regulatory** | CRITICAL | Could be classified as financial advisor, money transmitter |
| **Liability**        | CRITICAL | User loses money → who's responsible?                       |
| **Technical**        | HIGH     | Bug in code = real money lost, not recoverable              |
| **Reputation**       | HIGH     | One bad auto-trade = user leaves + bad reviews              |
| **Support**          | MEDIUM   | "Your bot lost my money" support tickets                    |

## Decision

**DEFER auto-trading to Phase 4+** (after paper trading validation in Sprint 3.3)

### Phased Implementation Approach

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AUTO-TRADING IMPLEMENTATION PHASES                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Phase 3 (Sprints 3.2-3.3): FOUNDATION                                  │
│  ├── Sprint 3.2: Exchange connection (READ-ONLY first)                  │
│  ├── Sprint 3.2b: 2FA/TOTP (security before API keys)                   │
│  └── Sprint 3.3: Paper trading (simulated trades, validation)           │
│                                                                         │
│  Phase 4 (Sprint 4.1): SEMI-AUTO                                        │
│  ├── "One-Click Trade" button (user confirms each trade)                │
│  ├── Trade size limits (max 5% of portfolio per trade)                  │
│  ├── Legal consent modal (explicit acknowledgment)                      │
│  └── Trade audit log                                                    │
│                                                                         │
│  Phase 5 (Sprint 4.2+): FULL AUTO (OPTIONAL - only if validated)        │
│  ├── Auto-pilot toggle with multiple safeguards                         │
│  ├── Daily loss limit (stop if -5% daily)                               │
│  ├── Confidence threshold (only trade if >85% confidence)               │
│  ├── Kill switch (instant disable)                                      │
│  └── Enhanced audit logging + email alerts                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Rationale

### Why Defer?

1. **Legal/Regulatory Risk**: Auto-trading with user funds could classify PulsAI as:
   - Financial advisor (requires licenses)
   - Money transmitter (requires licenses in many jurisdictions)
   - Investment manager (fiduciary responsibility)

2. **Liability Concerns**: If auto-trade loses user money:
   - Who is responsible?
   - Terms of Service must be bulletproof
   - May need legal review before implementation

3. **Technical Risk**: Bugs in auto-trading code:
   - Real money lost, not recoverable
   - Exchange API issues = stuck orders
   - Latency = slippage
   - Model overconfidence = bad trades

4. **Validation Required**: Must prove strategy works first:
   - Paper trading (Sprint 3.3) validates profitability
   - Without validation, auto-trading is gambling

### Why Not Skip Entirely?

- Competitive feature (some users want hands-off)
- Higher engagement for power users
- Revenue opportunity (premium feature)

## Safety Requirements (When Implemented)

### Legal Consent Modal

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ⚠️ AUTO-TRADING CONSENT                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  By enabling auto-trading, you acknowledge:                             │
│                                                                         │
│  □ I understand that automated trading involves SIGNIFICANT RISK        │
│  □ I may LOSE some or ALL of my invested capital                        │
│  □ Past performance does NOT guarantee future results                   │
│  □ PulsAI is NOT a financial advisor and does NOT provide               │
│    investment advice                                                    │
│  □ I am solely responsible for my trading decisions                     │
│  □ I have read and agree to the Terms of Service                        │
│                                                                         │
│  I confirm I am a resident of: [Country Dropdown]                       │
│  ⚠️ Auto-trading may not be available in your jurisdiction              │
│                                                                         │
│  [Cancel]                              [I Understand, Enable Auto-Trade]│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Technical Safeguards

| Safeguard                | Description                                       | Default  |
| ------------------------ | ------------------------------------------------- | -------- |
| **Daily Loss Limit**     | Stop trading if daily loss exceeds threshold      | -5%      |
| **Confidence Threshold** | Only execute if signal confidence above threshold | 85%      |
| **Position Size Limit**  | Max percentage of portfolio per trade             | 5%       |
| **Max Daily Trades**     | Limit number of trades per day                    | 10       |
| **Kill Switch**          | Instant disable button, always visible            | N/A      |
| **Audit Log**            | Complete history of all auto-trades               | Required |
| **Email Alerts**         | Notification on every auto-trade                  | Required |

## Alternatives Considered

### Option A: No Auto-Trade Ever (Rejected)

**Pros:**

- Zero liability
- Simpler product

**Cons:**

- Less competitive
- Limits power user engagement

**Verdict:** Too restrictive, limits product potential

### Option B: Auto-Trade in MVP (Rejected)

**Pros:**

- Competitive from day one

**Cons:**

- High legal risk before validation
- No paper trading proof of concept
- Support burden before product-market fit

**Verdict:** Too risky for MVP

### Option C: Phased Approach (Chosen)

**Pros:**

- Build trust gradually
- Validate with paper trading first
- Legal consent protects platform
- Can abort if issues arise

**Cons:**

- Delayed competitive feature
- More complex roadmap

**Verdict:** Best balance of opportunity and risk

## Consequences

### Positive

1. **Lower Liability**: MVP has no auto-trading = no trading losses to blame on platform
2. **Safer MVP**: Focus on signal quality, not trade execution
3. **Validation Path**: Paper trading proves value before real money
4. **Legal Buffer**: Time to review Terms of Service and compliance

### Negative

1. **Delayed Feature**: Competitors with auto-trading may attract users
2. **More Manual Work**: Users must execute trades themselves initially
3. **Complex Roadmap**: More sprints before full feature set

### Mitigations

- Sprint 1.6: Show "Auto-Trade Coming Soon" placeholder
- Paper trading in Sprint 3.3 demonstrates automation capability
- Fast-track Phase 4 if demand proven

## Implementation Timeline

| Sprint | Phase | Feature               | Risk Level |
| ------ | ----- | --------------------- | ---------- |
| 3.2    | 3     | Exchange read-only    | Low        |
| 3.2b   | 3     | 2FA security          | Low        |
| 3.3    | 3     | Paper trading         | Low        |
| 4.1    | 4     | Semi-auto (one-click) | Medium     |
| 4.2    | 5     | Full auto-pilot       | High       |

## Related Documents

- [ROADMAP.md](../01-business/ROADMAP.md) - Sprint 4.1, 4.2 entries
- [FEATURES.md](../03-functional/FEATURES.md) - Feature specification
- [SECURITY_GUIDELINES.md](../07-security/SECURITY_GUIDELINES.md) - API key handling

## Decision Makers

- Main Architect (PulsAI)

## Decision Date

2026-01-29
