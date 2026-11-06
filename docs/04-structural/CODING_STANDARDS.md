# PulsAI Coding Standards

## Overview

This document defines mandatory coding standards for ALL code in PulsAI (backend AND frontend). These are not guidelines - they are REQUIREMENTS.

**Golden Rule**: Code must be EXPLICIT, not clever. Readability > brevity.

> **MANDATORY CHECKLIST**: Before writing ANY code, complete the [Architect Checklist](./ARCHITECT_CHECKLIST.md).
> This includes: auditing for reusable code, TDD, verification commands, and more.
>
> **WHERE to put code:** [Module Map](./MODULE_MAP.md) (capability → backend layer / frontend SoT paths). Backend layer imports: `apps/api/pyproject.toml` → `[tool.importlinter]`; run `lint-imports` on cross-layer changes.

**Product and feature plans** (e.g. under `.cursor/plans/`): each plan should include a **Definition of Done** per phase — behavior-first tests (TDD where applicable), regression coverage for touched flows, and **verification gates** (`./scripts/verify.sh` for `apps/api`, `pnpm verify` for `apps/web`) plus coverage expectations on **new/changed** code per §9 below — so plans meet the same bar as application code.

---

## 0. Agent Workflow Protocol (MANDATORY)

This project uses structured agent workflows as a required execution layer for both backend and frontend work.

### 0.1 Scope

- Applies to **both FE and BE**.
- Applies to feature design, implementation, and architecture refactors.
- Does **not** replace CI/lint/type/test enforcement; it strengthens pre-implementation rigor.

### 0.2 Approved Skills and Trigger Conditions

Use these workflow skills from [mattpocock/skills](https://github.com/mattpocock/skills):

| Skill                              | Mandatory trigger                                                            |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| `/grill-me`                        | Any medium/large design with ambiguity or trade-offs                         |
| `/grill-with-docs`                 | Same as grill-me **and** you want CONTEXT.md / ADR paper trail this session  |
| `/prd-to-plan` or `/prd-to-issues` | Any multi-sprint or dependency-heavy feature                                 |
| `/tdd`                             | Any behavior change (new feature, bug fix, regression fix, contract change)  |
| `/improve-codebase-architecture`   | Weekly architecture hygiene or after large delivery bursts                   |
| `/codebase-design`                 | Vocabulary only when shaping a **named** module (interface / seam / depth)   |
| `/domain-modeling`                 | When domain **words** are the problem (ubiquitous language / glossary / ADR) |
| `/diagnosing-bugs`                 | Hard bug / flake / named regression — user invokes; not casual Q&A           |
| `/resolving-merge-conflicts`       | In-progress merge/rebase with conflict markers — finish intent-first         |
| `/triage`                          | Inbound external issues only — recommend-and-wait; not self-authored tickets |
| `/wayfinder`                       | Multi-session foggy effort — decision map only; plan don't code              |
| `/prototype`                       | One unresolved design question — throwaway probe; never merge to master      |
| `/research`                        | External primary-source facts — one Sonnet subagent; notes in `.scratch/`    |
| `/code-review`                     | Standards+Spec review since a fixed point (committed); not bug-hunt review   |
| `/implement`                       | One settled ticket/spec — TDD build on current branch; never redesign        |
| `/to-spec`                         | Multi-session decided work → one tracker **spec** issue; seams first         |
| `/to-tickets`                      | Spec/plan → tracer-bullet tickets with blockers; quiz before publish         |

`/codebase-design` is a **shared glossary** ([aihero](https://www.aihero.dev/skills-codebase-design)), not a process. Do not point a session at it and say "go" — that burns tokens redesigning unasked modules. Sit it under `/grill-me`, `/improve-codebase-architecture`, or `/tdd`.

`/domain-modeling` is the **active** domain glossary ([aihero](https://www.aihero.dev/skills-domain-modeling)): write resolved terms into root `CONTEXT.md` inline; ADRs only into `docs/08-adr/` after the three-bar test. Never dump specs into `CONTEXT.md`.

`/diagnosing-bugs` is a **six-phase hard-bug loop** ([aihero](https://www.aihero.dev/skills-diagnosing-bugs)): no theory until a tight red-capable repro exists. PulsAI keeps it **user-invoked** to avoid over-fire on quick questions.

`/resolving-merge-conflicts` finishes a stalled merge/rebase ([aihero](https://www.aihero.dev/skills-resolving-merge-conflicts)): primary sources over `--ours`/`--theirs`; verify before finish commit; never stash foreign dirty files.

`/triage` is the **inbound** issue on-ramp ([aihero](https://www.aihero.dev/skills-triage)): external reports only; recommend then wait; tracker config in `docs/agents/`. Do not triage tickets from `/prd-to-issues` or `/to-tickets`.

`/wayfinder` is **multi-session planning** ([aihero](https://www.aihero.dev/skills-wayfinder)): decision tickets on a map; never product code mid-map. One-session work stays on `/grill-me`. Cleared map → plan/spec, not implement.

`/prototype` settles **one** ungrillable design question ([aihero](https://www.aihero.dev/skills-prototype)): throwaway HTML/UI variants; evidence on `prototype/<name>`; never merge into master. Settled work uses `/tdd`.

`/research` gathers **cited primary-source facts** ([aihero](https://www.aihero.dev/skills-research)): one Sonnet subagent, no nesting (#530); file under `.scratch/research/` (ephemeral).

`/code-review` is **Standards + Spec** on `<fixed-point>...HEAD` ([aihero](https://www.aihero.dev/skills-code-review)): two Sonnet axes, never merged; not Claude's built-in bug-hunt `/code-review`; not `/caveman-review`.

`/implement` builds **already-decided** work ([aihero](https://www.aihero.dev/skills-implement)): one ticket per session; PulsAI `/tdd` + verify; interim commit before `/code-review`; never redesign mid-build.

`/grill-with-docs` is single-session planning **with a paper trail** ([aihero](https://www.aihero.dev/skills-grill-with-docs)): `/grilling` + `/domain-modeling`. Prefer `/grill-me` without docs; `/wayfinder` for multi-session.

`/to-spec` records **already-made** decisions as one tracker **spec** ([aihero](https://www.aihero.dev/skills-to-spec)): seams confirmed first; no interview; multi-session only. Sibling to PulsAI `/prd-to-plan` (local contracts plan). Cleared `/wayfinder` map → `/to-spec #<map>`. Parent `ready-for-agent` is not an AFK “build the whole spec” order — cut tickets next.

`/to-tickets` cuts a settled **spec**/plan into **tracer-bullet** tickets ([aihero](https://www.aihero.dev/skills-to-tickets)): quiz before publish; vertical slices with blocking edges; prefer GitHub `--parent` / `--blocked-by`. Sibling to PulsAI `/prd-to-issues`. Do not triage; then `/implement` one frontier ticket per session.

**Primary keys (high-churn):** new append-heavy tables use bigint identity (optional `public_id` UUID) — see [`ADR-023`](../08-adr/ADR-023-primary-keys-high-churn.md). Do not big-bang migrate existing UUID PKs.

### 0.3 Required Order of Execution

1. Clarify and challenge assumptions using `/grill-me` when trigger applies.
2. Convert work into vertical slices with `/prd-to-plan`, `/prd-to-issues`, or (multi-session) `/to-spec` → `/to-tickets` when trigger applies.
3. Execute each slice with `/tdd` (red-green-refactor, behavior-first tests).
4. Run architecture hygiene with `/improve-codebase-architecture` when trigger applies.
5. Run project verification gates:
   - Backend: `cd apps/api && ./scripts/verify.sh`
   - Frontend: `cd apps/web && pnpm verify`

### 0.4 Source of Truth and Conflict Resolution

- Policy authority remains in `.cursorrules` and this document.
- Skills define process flow, not policy overrides.
- If skill output conflicts with project standards, project standards win.

---

## 1. SOLID Principles (MANDATORY)

### 1.1 Single Responsibility Principle (SRP)

Every class, function, and module must have ONE reason to change.

**Python (Backend):**

```python
# BAD - God class doing multiple things
class TradingBot:
    def fetch_market_data(self): ...
    def calculate_indicators(self): ...
    def train_model(self): ...
    def execute_trade(self): ...
    def send_notification(self): ...
    def log_to_database(self): ...

# GOOD - Single responsibility per class
class MarketDataService:
    """Fetches and normalizes market data from exchanges."""
    def fetch_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame: ...

class IndicatorCalculator:
    """Calculates technical indicators from price data."""
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series: ...

class TradeExecutor:
    """Executes trades on exchanges via API."""
    def execute_order(self, order: Order) -> OrderResult: ...

class NotificationService:
    """Sends notifications to users."""
    def send_email(self, to: str, subject: str, body: str) -> bool: ...
```

**TypeScript (Frontend):**

```typescript
// BAD - Component doing too much
function Dashboard() {
  const [data, setData] = useState();
  const [user, setUser] = useState();

  // Fetching data
  useEffect(() => { ... }, []);

  // Processing data
  const processedData = useMemo(() => { ... }, [data]);

  // Formatting dates
  const formatDate = (d: Date) => { ... };

  // Calculating metrics
  const totalProfit = data?.reduce(...);

  return <div>...</div>;
}

// GOOD - Separated concerns
// hooks/usePortfolioData.ts
function usePortfolioData(userId: string) {
  return useQuery({
    queryKey: ['portfolio', userId],
    queryFn: () => fetchPortfolio(userId),
  });
}

// utils/dateFormatter.ts
export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US').format(date);
}

// components/Dashboard.tsx
function Dashboard() {
  const { data, isLoading } = usePortfolioData(userId);

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  return <PortfolioSummary data={data} />;
}
```

### 1.2 Open/Closed Principle (OCP)

Open for extension, closed for modification.

```python
# BAD - Adding new exchange requires modifying existing code
class ExchangeClient:
    def execute_trade(self, exchange: str, order: Order):
        if exchange == "binance":
            return self._binance_trade(order)
        elif exchange == "kraken":
            return self._kraken_trade(order)
        elif exchange == "bitget":  # Adding new exchange = modifying class
            return self._bitget_trade(order)

# GOOD - Strategy pattern, extend without modifying
from abc import ABC, abstractmethod

class ExchangeClient(ABC):
    @abstractmethod
    def execute_trade(self, order: Order) -> OrderResult:
        pass

class BinanceClient(ExchangeClient):
    def execute_trade(self, order: Order) -> OrderResult:
        # Binance-specific implementation
        pass

class KrakenClient(ExchangeClient):
    def execute_trade(self, order: Order) -> OrderResult:
        # Kraken-specific implementation
        pass

# Adding new exchange = NEW class, no modifications to existing
class BitgetClient(ExchangeClient):
    def execute_trade(self, order: Order) -> OrderResult:
        # Bitget-specific implementation
        pass
```

### 1.3 Liskov Substitution Principle (LSP)

Subtypes must be substitutable for their base types.

```python
# BAD - Subclass breaks parent contract
class Bird:
    def fly(self) -> None:
        print("Flying")

class Penguin(Bird):
    def fly(self) -> None:
        raise Exception("Penguins can't fly!")  # Violates LSP

# GOOD - Proper abstraction
class Bird(ABC):
    @abstractmethod
    def move(self) -> None:
        pass

class FlyingBird(Bird):
    def move(self) -> None:
        self.fly()

    def fly(self) -> None:
        print("Flying")

class Penguin(Bird):
    def move(self) -> None:
        self.swim()

    def swim(self) -> None:
        print("Swimming")
```

### 1.4 Interface Segregation Principle (ISP)

No client should be forced to depend on interfaces it doesn't use.

```python
# BAD - Fat interface
class ITradingBot(ABC):
    @abstractmethod
    def fetch_data(self): pass

    @abstractmethod
    def analyze(self): pass

    @abstractmethod
    def train_model(self): pass  # Not all bots need ML

    @abstractmethod
    def execute_trade(self): pass

    @abstractmethod
    def send_telegram(self): pass  # Not all bots need Telegram

# GOOD - Segregated interfaces
class IDataFetcher(ABC):
    @abstractmethod
    def fetch_data(self, symbol: str) -> DataFrame: pass

class IAnalyzer(ABC):
    @abstractmethod
    def analyze(self, data: DataFrame) -> Signal: pass

class ITradeExecutor(ABC):
    @abstractmethod
    def execute(self, signal: Signal) -> Trade: pass

class INotifier(ABC):
    @abstractmethod
    def notify(self, message: str) -> bool: pass
```

### 1.5 Dependency Inversion Principle (DIP)

Depend on abstractions, not concretions.

```python
# BAD - Direct dependency on concrete class
class SignalGenerator:
    def __init__(self):
        self.data_source = BinanceAPI()  # Tightly coupled
        self.database = PostgresDB()      # Can't test without real DB

    def generate(self, symbol: str) -> Signal:
        data = self.data_source.fetch(symbol)
        # ...

# GOOD - Depend on abstractions
class SignalGenerator:
    def __init__(
        self,
        data_source: IDataSource,  # Interface
        repository: ISignalRepository,  # Interface
    ):
        self.data_source = data_source
        self.repository = repository

    def generate(self, symbol: str) -> Signal:
        data = self.data_source.fetch(symbol)
        # ...

# In production
generator = SignalGenerator(
    data_source=BinanceDataSource(),
    repository=PostgresSignalRepository(),
)

# In tests
generator = SignalGenerator(
    data_source=MockDataSource(),
    repository=InMemorySignalRepository(),
)
```

---

## 2. NO-DRY Violations (Don't Repeat Yourself)

### 2.0 DON'T REINVENT THE WHEEL (CRITICAL)

> **Before writing ANY new code, AUDIT the existing codebase!**

```
MANDATORY AUDIT CHECKLIST:
□ Searched for existing HOOKS that do similar things?
□ Searched for existing HELPERS/UTILS?
□ Searched for existing COMPONENTS?
□ Searched for existing CLASSES/SERVICES?
□ Searched for existing INTERFACES/TYPES/SCHEMAS?
□ Searched for existing CONSTANTS?

Frontend folders to check:
  - @/lib/utils/, @/hooks/, @/components/ui/, @/types/, @/schemas/

Backend folders to check:
  - src/lib/utils/, src/application/services/, src/domain/services/
  - src/application/schemas/, src/infrastructure/
```

**WHY**: Creating new code when existing code does the same = DRY violation + inconsistency + new bugs.

**A trade walk is never written again** (BACKTEST-ONE, 2026-10-18): turning a book's bars + calls into trades and money
is the engine's (`CryptoBacktester`). Call it -- or its clients `stance_trades` / `model_trades` -- never a new loop over
`walk_thin_stop_trade`. Five walks became one after they disagreed on fills, liquidation and venue; the registry row and
the kernel-caller ratchet refuse a sixth (see [MODULE_MAP.md](./MODULE_MAP.md) § One trade walk).

See [ARCHITECT_CHECKLIST.md](./ARCHITECT_CHECKLIST.md) for full audit commands.

### 2.1 When DRY Applies

```python
# BAD - Repeated logic
def calculate_binance_fee(amount: float) -> float:
    return amount * 0.001

def calculate_kraken_fee(amount: float) -> float:
    return amount * 0.001

def calculate_bitget_fee(amount: float) -> float:
    return amount * 0.001

# GOOD - Abstracted
def calculate_fee(amount: float, fee_rate: float = 0.001) -> float:
    return amount * fee_rate
```

### 2.2 When DRY DOESN'T Apply (Avoid Wrong Abstraction)

```python
# BAD - Over-abstraction (looks similar but different domains)
def process_thing(data, type, mode, config):
    if type == "user":
        # 50 lines of user logic
    elif type == "trade":
        # 50 lines of trade logic
    elif type == "signal":
        # 50 lines of signal logic

# GOOD - Separate functions (similar code != same responsibility)
def process_user(user_data: UserData) -> User:
    # User-specific logic
    pass

def process_trade(trade_data: TradeData) -> Trade:
    # Trade-specific logic
    pass

def process_signal(signal_data: SignalData) -> Signal:
    # Signal-specific logic
    pass
```

---

## 3. Explicit Code (NO Clever Code)

### 3.1 No Ternary for Complex Logic

```python
# BAD - Ternary operator for non-trivial logic
signal = "BUY" if rsi < 30 and macd > 0 and volume_ratio > 1.5 else "SELL" if rsi > 70 else "HOLD"

# GOOD - Explicit if/else
def determine_signal(rsi: float, macd: float, volume_ratio: float) -> str:
    if rsi < 30 and macd > 0 and volume_ratio > 1.5:
        return "BUY"

    if rsi > 70:
        return "SELL"

    return "HOLD"
```

```typescript
// BAD - Nested ternaries
const status = isLoading ? 'loading' : error ? 'error' : data ? 'success' : 'idle';

// GOOD - Explicit function
function getStatus(isLoading: boolean, error: Error | null, data: Data | null): Status {
  if (isLoading) {
    return 'loading';
  }

  if (error) {
    return 'error';
  }

  if (data) {
    return 'success';
  }

  return 'idle';
}
```

### 3.2 Early Returns (Guard Clauses)

```python
# BAD - Nested conditions
def process_trade(trade: Trade) -> Result:
    if trade is not None:
        if trade.is_valid():
            if trade.has_sufficient_balance():
                if not trade.is_duplicate():
                    # Actual logic buried deep
                    return execute(trade)
                else:
                    return Error("Duplicate")
            else:
                return Error("Insufficient balance")
        else:
            return Error("Invalid trade")
    else:
        return Error("No trade")

# GOOD - Guard clauses with early returns
def process_trade(trade: Trade) -> Result:
    if trade is None:
        return Error("No trade")

    if not trade.is_valid():
        return Error("Invalid trade")

    if not trade.has_sufficient_balance():
        return Error("Insufficient balance")

    if trade.is_duplicate():
        return Error("Duplicate")

    return execute(trade)
```

### 3.3 Meaningful Names

```python
# BAD
def calc(d, t):
    return d * t * 0.001

# GOOD
def calculate_trading_fee(trade_amount: Decimal, fee_rate: Decimal) -> Decimal:
    """Calculate trading fee for a given trade amount."""
    return trade_amount * fee_rate
```

---

## 4. Error Handling

### 4.1 Never Swallow Exceptions

```python
# BAD - Silent failure
try:
    result = execute_trade(order)
except Exception:
    pass  # NEVER DO THIS

# GOOD - Handle or re-raise
try:
    result = execute_trade(order)
except InsufficientBalanceError as e:
    logger.warning(f"Insufficient balance for order {order.id}: {e}")
    return OrderResult.failed(reason="insufficient_balance")
except ExchangeAPIError as e:
    logger.error(f"Exchange API error: {e}")
    raise  # Re-raise for caller to handle
except Exception as e:
    logger.exception(f"Unexpected error executing trade: {e}")
    raise TradingError(f"Failed to execute trade: {e}") from e
```

### 4.2 Custom Exceptions

```python
# Define domain-specific exceptions
class PulsAIError(Exception):
    """Base exception for PulsAI."""
    pass

class TradingError(PulsAIError):
    """Error during trade execution."""
    pass

class InsufficientBalanceError(TradingError):
    """User doesn't have enough balance."""
    pass

class ExchangeAPIError(TradingError):
    """Exchange API returned an error."""
    def __init__(self, exchange: str, message: str, status_code: int):
        self.exchange = exchange
        self.status_code = status_code
        super().__init__(f"{exchange} API error ({status_code}): {message}")

class SignalError(PulsAIError):
    """Error in signal generation."""
    pass

class ModelError(PulsAIError):
    """Error in ML model."""
    pass
```

---

## 5. Type Safety

### 5.1 Python Type Hints (MANDATORY)

**Annotations are documentation the checker verifies (ANN-GATE, owner 2026-10-18: "annotations must be self-explanatory and good for understanding and traceability").** Five rules:

1. **Signatures, always.** Every parameter and every return is annotated -- product code, CLIs, the lab, ops scripts and tests. Product code is held by mypy `strict` + ruff `ANN`; everywhere else the `missing-annotation` row of `standards_rules` counts ruff `ANN001`-`ANN206` through every pyproject exemption and past `noqa`. A touched file lowers its count, a new file carries 0 (`check_touched_debt`, pre-commit and CI); the tree total may only fall (verify 2f-std).
2. **Locals only where inference cannot reach them.** An empty container (`rows: list[Fill] = []`), a `None` start (`best: Fill | None = None`), the return of an untyped library. Everywhere else leave it to the checker: it infers the type and verifies it, while a hand-copied local type drifts the day the right-hand side changes.
3. **No new value of unknown type.** A bare `list` / `dict`, an empty literal nobody typed, an untyped library's return: basedpyright cannot name the type, so nothing downstream of it is checked. The `unknown-type` row counts basedpyright's `reportUnknown*` / `reportMissingTypeArgument` over product code with a config of its own (the root `pyrightconfig.json` keeps them off, so the editor and the pre-push gate are unchanged); same touch-to-lower rule and tree ratchet.
4. **A named schema at every boundary, never `dict[str, Any]`.** Pydantic where data must be validated (a request, a file, a venue reply); `TypedDict` for an internal dict payload; a `@dataclass(frozen=True)` for a value object.
5. **Self-explanatory domain types.** `NewType` for units the code mixes up (`Bps`, `Usd`, bars vs rows -- a count needs its unit in the type); `Literal` or an `Enum` for a closed set (sides, tiers, window roles); `Final` for constants; a `Protocol` for a seam, naming only what the caller reads -- `PoolEntry` in `src/infrastructure/db_pool_checkout_trace.py` is SQLAlchemy's `ConnectionPoolEntry` reduced to the one `info` dict the listeners touch.

**`Any` is a ratchet, not a type (P1-14):** write the shape down -- a `TypedDict` / dataclass / pydantic model for a known payload (`dict[str, Any]` is ~two thirds of the references; the count is `BASELINE_ANY_REFERENCES`), a `Protocol` for a known interface, `object` plus narrowing for a truly unknown value; `Any` only at an untyped third-party boundary. Gate: `apps/api/src/lib/quality_gates/explicit_any.py` -- the `explicit-any` row of `scripts/check_touched_debt.py` (pre-commit, CI: a touched file pays its own count down, a new file carries none except what a split moved in) and verify step 2f-any (the tree total may only fall).

```python
# BAD - No type hints
def process_signal(data, threshold):
    if data['confidence'] > threshold:
        return {'action': 'BUY', 'price': data['price']}
    return None

# GOOD - Full type hints
from typing import Optional
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class SignalData:
    symbol: str
    confidence: float
    price: Decimal
    timestamp: datetime

@dataclass
class TradeAction:
    action: Literal["BUY", "SELL", "HOLD"]
    price: Decimal
    reason: str

def process_signal(
    data: SignalData,
    confidence_threshold: float = 0.75,
) -> Optional[TradeAction]:
    """
    Process a trading signal and return action if confidence meets threshold.

    Args:
        data: The signal data to process
        confidence_threshold: Minimum confidence to act (default 0.75)

    Returns:
        TradeAction if confidence meets threshold, None otherwise
    """
    if data.confidence > confidence_threshold:
        return TradeAction(
            action="BUY",
            price=data.price,
            reason=f"Confidence {data.confidence:.2f} > {confidence_threshold}",
        )

    return None
```

### 5.2 TypeScript Strict Mode (MANDATORY)

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true
  }
}
```

### 5.3 Validation with Valibot (NOT Zod)

> **IMPORTANT**: We use **Valibot** (not Zod) for frontend validation.
> Valibot is 10x smaller (1.37KB vs 17.7KB) and used in existing projects.

**Frontend Validation Examples:**

```typescript
// schemas/trade.schemas.ts
import * as v from 'valibot';

// ✅ GOOD - Valibot schema with explicit validation
export const CreateTradeSchema = v.object({
  symbol: v.pipe(
    v.string(),
    v.minLength(5, 'Symbol must be at least 5 characters (e.g., BTC/USDT)'),
    v.regex(/^[A-Z]{3,5}\/[A-Z]{3,5}$/, 'Symbol must be in format BASE/QUOTE')
  ),
  side: v.picklist(['buy', 'sell'], 'Side must be buy or sell'),
  quantity: v.pipe(v.number(), v.minValue(0.00001, 'Quantity must be positive')),
  price: v.optional(v.pipe(v.number(), v.minValue(0, 'Price must be positive'))),
  stopLoss: v.optional(v.pipe(v.number(), v.minValue(0, 'Stop loss must be positive'))),
  takeProfit: v.optional(v.pipe(v.number(), v.minValue(0, 'Take profit must be positive'))),
});

// Infer TypeScript type from schema
export type CreateTradeInput = v.InferInput<typeof CreateTradeSchema>;
export type CreateTradeOutput = v.InferOutput<typeof CreateTradeSchema>;

// ✅ Usage in form or API handler
import { safeParse, flatten } from 'valibot';

function validateTradeInput(input: unknown): CreateTradeOutput | null {
  const result = safeParse(CreateTradeSchema, input);

  if (!result.success) {
    const errors = flatten(result.issues);
    console.error('Validation errors:', errors);
    return null;
  }

  return result.output;
}
```

**API Route Validation:**

```typescript
// app/api/trades/route.ts
import * as v from 'valibot';
import { NextRequest, NextResponse } from 'next/server';
import { CreateTradeSchema } from '@/schemas/trade.schemas';

export async function POST(request: NextRequest) {
  const body = await request.json();

  // Validate with Valibot
  const result = v.safeParse(CreateTradeSchema, body);

  if (!result.success) {
    return NextResponse.json(
      {
        error: 'Validation failed',
        details: v.flatten(result.issues).nested,
      },
      { status: 400 }
    );
  }

  // result.output is fully typed
  const trade = result.output;

  // ... process trade
}
```

**Form Validation with React Hook Form:**

```typescript
// hooks/useTradeForm.ts
import { useForm } from 'react-hook-form';
import { valibotResolver } from '@hookform/resolvers/valibot';
import { CreateTradeSchema, type CreateTradeInput } from '@/schemas/trade.schemas';

export function useTradeForm() {
  return useForm<CreateTradeInput>({
    resolver: valibotResolver(CreateTradeSchema),
    defaultValues: {
      symbol: 'BTC/USDT',
      side: 'buy',
      quantity: 0.001,
    },
  });
}
```

**Why NOT Zod:**

| Comparison   | Valibot      | Zod          |
| ------------ | ------------ | ------------ |
| Bundle Size  | **1.37 KB**  | 17.7 KB      |
| Tree-shaking | ✅ Excellent | ⚠️ Limited   |
| API          | Same pattern | Same pattern |

**Decision**: Valibot for 90% smaller bundle.

````

```typescript
// BAD - any type
function processData(data: any): any {
  return data.value * 2;
}

// GOOD - Proper types
interface SignalData {
  symbol: string;
  confidence: number;
  price: number;
  timestamp: Date;
}

interface ProcessedSignal {
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  reason: string;
}

function processSignal(data: SignalData): ProcessedSignal {
  if (data.confidence > 0.75) {
    return {
      action: 'BUY',
      confidence: data.confidence,
      reason: `High confidence signal for ${data.symbol}`,
    };
  }

  return {
    action: 'HOLD',
    confidence: data.confidence,
    reason: 'Confidence below threshold',
  };
}
````

### 5.4 TanStack Query (Frontend — MANDATORY when needed)

**Rule**: For all **server state** (GET) and **mutations** (POST/PUT/DELETE) that touch the backend API, you **MUST** use **TanStack Query** (`useQuery` / `useMutation`). Fetchers **MUST** live in `@/config/queryFetchers.ts` (or its split modules); query/mutation keys **MUST** live in `@/config/queryKeys.ts`. All fetchers use `appFetch` from `@/services/api` (single entry point for auth, retry, timeout).

**When it applies:**

- **useQuery**: Any GET that loads server data (lists, detail, config). Enables cache, deduplication, and invalidation.
- **useMutation**: Any POST/PUT/DELETE that changes server state or triggers a one-shot action (e.g. run backtest, run optimize, save comparison). Enables loading/error state and consistent key usage.

**SoT:**

- **Keys**: `@/config/queryKeys.ts` — one factory per resource (e.g. `backtestHubOptimizeKeys()`, `backtestHubWalkForwardOptimizeKeys()`).
- **Fetchers**: `@/config/queryFetchers*.ts` — pure async functions that call `appFetch` and return typed data; re-exported from `@/config/queryFetchers.ts`.

**Do NOT:**

- Call `authenticatedFetch` or `fetch` directly from pages/hooks for API that should be cached or tracked as server state. Use the config fetchers + `useQuery`/`useMutation` instead.
- Put fetcher logic in feature folders without also exposing it from config (config is the single import path for TanStack Query).

**Reference**: [DATA_LAYER_AND_CHART_SOT.md](./DATA_LAYER_AND_CHART_SOT.md).

---

## 6. Documentation Standards

### 6.1 Python Docstrings

```python
def calculate_position_size(
    account_balance: Decimal,
    risk_per_trade: float,
    entry_price: Decimal,
    stop_loss_price: Decimal,
) -> Decimal:
    """
    Calculate position size based on risk management rules.

    Uses the formula: position_size = (balance * risk) / (entry - stop_loss)

    Args:
        account_balance: Total account balance in quote currency (e.g., USDT)
        risk_per_trade: Maximum risk per trade as decimal (e.g., 0.02 for 2%)
        entry_price: Expected entry price
        stop_loss_price: Stop loss price level

    Returns:
        Position size in base currency units

    Raises:
        ValueError: If stop_loss_price >= entry_price (for long positions)
        ValueError: If risk_per_trade > 0.1 (max 10% risk)

    Example:
        >>> calculate_position_size(
        ...     account_balance=Decimal("10000"),
        ...     risk_per_trade=0.02,
        ...     entry_price=Decimal("50000"),
        ...     stop_loss_price=Decimal("49000"),
        ... )
        Decimal("0.2")  # 0.2 BTC
    """
    if stop_loss_price >= entry_price:
        raise ValueError("Stop loss must be below entry price for long positions")

    if risk_per_trade > 0.1:
        raise ValueError("Risk per trade cannot exceed 10%")

    risk_amount = account_balance * Decimal(str(risk_per_trade))
    price_risk = entry_price - stop_loss_price

    return risk_amount / price_risk
```

### 6.2 TypeScript JSDoc

````typescript
/**
 * Calculate the profit/loss for a closed trade.
 *
 * @param entry - Entry price of the trade
 * @param exit - Exit price of the trade
 * @param size - Position size in base currency
 * @param side - Trade direction ('LONG' or 'SHORT')
 * @param feeRate - Trading fee rate (default 0.001 = 0.1%)
 * @returns Profit/loss in quote currency
 *
 * @example
 * ```ts
 * const pnl = calculatePnL({
 *   entry: 50000,
 *   exit: 51000,
 *   size: 0.1,
 *   side: 'LONG',
 * });
 * // Returns: 100 - fees
 * ```
 */
function calculatePnL({
  entry,
  exit,
  size,
  side,
  feeRate = 0.001,
}: {
  entry: number;
  exit: number;
  size: number;
  side: 'LONG' | 'SHORT';
  feeRate?: number;
}): number {
  const grossPnL = side === 'LONG' ? (exit - entry) * size : (entry - exit) * size;

  const fees = (entry * size + exit * size) * feeRate;

  return grossPnL - fees;
}
````

---

## 7. File Organization

### 7.1 One Export Per File (Preferred)

```
# GOOD - Clear, single responsibility
src/
  services/
    market_data_service.py      # One class
    signal_service.py           # One class
    trade_executor_service.py   # One class

  repositories/
    trade_repository.py         # One interface + implementation
    signal_repository.py        # One interface + implementation
```

### 7.2 Maximum File Length

| File Type                        | Max Lines | Enforced by                                                                                       |
| -------------------------------- | --------- | ------------------------------------------------------------------------------------------------- |
| **Python** (`apps/api/src`)      | 400       | `apps/api/scripts/check_file_size_baseline.py`                                                    |
| **TypeScript** (`apps/web/src`)  | 400       | the SAME gate — one rule, both languages                                                          |
| **Hard ceiling, either side**    | 500       | same gate, reported: owes a SPLIT, not a re-record                                                |
| **Page components** (`page.tsx`) | 600       | `max-lines: warn` -- and a warn BLOCKS: `pnpm lint` and lint-staged run `eslint --max-warnings=0` |
| **Test files / `.d.ts`**         | No limit  | skipped by the gate; `max-lines: off` in ESLint                                                   |

**The research lab is NOT exempt** (owner, 2026-10-04): `apps/api/src/research` is gated exactly like product code, on the tree scan and on the pre-commit touch path.

**ONE gate, both languages** (owner, 2026-09-18: the cap "must also go for FE, not only BE").
ESLint's `max-lines` stays as a fast in-editor hint, but it cannot be the source of truth for a cap
defined as "without imports": it has `skipBlankLines` and `skipComments` but no way to skip
imports, and it is a `warn`. So `check_file_size_baseline.py` measures both `apps/api/src` (`.py`)
and `apps/web/src` (`.ts`/`.tsx`) and is what the standard means. Note the two disagree by design:
ESLint skips comments, the gate counts them.

**The count is EFFECTIVE lines, not file length** (owner, 2026-09-18: "400-500 max lines
without imports, typecheching etc"). An effective line is a physical line that is not a
module-level import, not part of the `if TYPE_CHECKING:` block, not the module docstring, and not
blank. This mirrors what ESLint already does on the TS side with `skipBlankLines` — the two
languages now measure the same thing.

MEASURED over the 1,929 modules in `apps/api/src` on the day the metric changed:

| counted as                      | files over 400 |
| ------------------------------- | -------------- |
| physical lines (the old gate)   | 87             |
| effective lines (this standard) | 31             |
| released by counting code only  | 56             |
| still over the 500 ceiling      | 14             |

Fifty-six files were being charged for scaffolding rather than for complexity — the two worst
carry 203 and 168 lines of imports and type-checking alone. **Comments still count**: in this repo
they carry the measured evidence behind a decision, and discounting them would invite the opposite
of what they are for.

On the TypeScript side an effective line is one that is not a module-level `import` / re-export and
not blank. Measured when the FE joined the gate: **one** file in `apps/web/src` exceeds 400
effective lines (`utils/chart-pane-heights.ts`, 464) — previously invisible, because ESLint only
warned. Read every number here from the gate, not from this page
(`.claude/rules/verify-and-judge-not-quote.md`).

**ESLint Configuration:**

```javascript
// eslint.config.mjs
'max-lines': ['warn', { max: 400, skipBlankLines: true, skipComments: true }],

// Page components get relaxed limit (they orchestrate many features)
// files: ['**/app/**/page.tsx']
'max-lines': ['warn', { max: 600, skipBlankLines: true, skipComments: true }],
```

**Notes:**

- Lines are counted excluding blank lines and comments
- If a file exceeds limits, split into smaller components/hooks/utils
- Use Atomic Design pattern: extract to molecules/organisms
- Providers, hooks, and services are not exempt. If a provider grows beyond ~120-150 lines or mixes context, side effects, storage, event wiring, formatting, and API orchestration, split it into co-located `types.ts`, `context.ts`, `helpers.ts`, and dedicated hooks before it becomes a God module.

### 7.2.1 Naming consistency for a feature (Backtest example)

Use one clear convention per concept so names are predictable and not confusing.

| Concept                   | Naming         | Meaning                                                                  | Where used                                                                                                                                        |
| ------------------------- | -------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Domain entity (noun)**  | `backtest_run` | A single backtest run (the saved record).                                | Domain: `BacktestRun`, file `domain/models/backtest_run.py`.                                                                                      |
| **Use case (verb)**       | `run_backtest` | The action "run a backtest".                                             | Application: `RunBacktestUseCase`, file `application/use_cases/run_backtest.py`. Matches pattern: `GenerateSignalUseCase` / `generate_signal.py`. |
| **Feature / flow (noun)** | `backtest_run` | The "backtest run" feature (endpoint + response + filter for that flow). | API: `backtest_run.py` (endpoint), `backtest_run_response.py`, and infrastructure filter used by the use case: `backtest_run_filter.py`.          |
| **Engine (noun)**         | `backtester`   | The simulation engine.                                                   | Infrastructure: `CryptoBacktester`, files `backtester.py`, `backtester_types.py`, `backtester_exits.py`, `backtester_metrics.py`.                 |

**Rule:** Use **verb_noun** for use cases (e.g. `run_backtest`, `generate_signal`). Use **noun** for entities, feature modules, and the engine (`backtest_run`, `backtester`). Do not mix without documenting; when adding a new file, choose the name from this table so the same concept always uses the same root.

### 7.3 Import Conventions (MANDATORY)

**ALWAYS use the `@/` path aliases defined in tsconfig.json for EVERY import in `src/`. NEVER use a relative import (`./` or `../`).**

**Path aliases (namespaces):** Use `@/components/`, `@/hooks/`, `@/types/`, etc. for every import — including a sibling in the same folder. `useTrainingJob/index.ts` imports its sibling as `import type { UseTrainingJobReturn } from '@/hooks/useTrainingJob/types'`, not `'./types'`. Do **not** use relative paths like `../../../components/X`, `../../hooks/useX`, or `./SiblingView`—they obscure location and drift; the `@/` form is globally grep-able and uniform. A broken alias after a folder move is caught immediately by `tsc`, so the uniformity carries no silent-hazard cost.

**Enforcement:** The [GitHub PR checklist](../../.github/PULL_REQUEST_TEMPLATE.md) requires `@/` aliases for all `src/` imports. **CI / Husky / pre-push** run `pnpm lint` on `@pulsai/web`, which enforces `pulsai-fe-imports/prefer-alias-imports` on `src/**` (error; flags any `./` or `../` import; suggests + auto-fixes to `@/`, `@/messages/`, or `@pulsai/shared/`). Auto-fix: `pnpm --filter @pulsai/web lint:fix` (or staged files via Husky). **`tests/`** may use relatives for fixtures and helpers. SoT: `apps/web/eslint-fe-import-aliases.mjs` (keep aligned with `tsconfig.json` `paths`; custom rule — not `eslint-plugin-paths` — so alias roots stay single-sourced).

**TypeScript (Frontend) - Path Aliases:**

```typescript
// ✅ GOOD - Use path aliases from tsconfig.json
import { SignalCard } from '@/components/SignalCard';
import { usePortfolioData } from '@/hooks/usePortfolioData';
import { formatCurrency } from '@/lib/utils';
import { Signal } from '@/types/signals';
import { ThemeProvider } from '@/providers/ThemeProvider';
import { locales } from '@/i18n/config';

// ❌ BAD - Relative imports (hard to refactor, unclear location)
import { SignalCard } from '../../../components/SignalCard';
import { usePortfolioData } from '../../hooks/usePortfolioData';

// ❌ BAD - Missing alias for shared package
import { Signal } from '../../../packages/shared/src/types';

// ✅ GOOD - Use alias for shared package
import { Signal } from '@pulsai/shared/types';
```

**Path Alias Configuration (tsconfig.json):**

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@/components/*": ["./src/components/*"],
      "@/hooks/*": ["./src/hooks/*"],
      "@/lib/*": ["./src/lib/*"],
      "@/types/*": ["./src/types/*"],
      "@/styles/*": ["./src/styles/*"],
      "@/i18n/*": ["./src/i18n/*"],
      "@/providers/*": ["./src/providers/*"],
      "@pulsai/shared/*": ["../../packages/shared/src/*"]
    }
  }
}
```

**Import Order (enforced by ESLint):**

```typescript
// 1. React imports
import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';

// 2. Next.js imports
import { useRouter } from 'next/navigation';
import type { Metadata } from 'next';

// 3. Third-party libraries
import { useTranslations } from 'next-intl';
import { useQuery } from '@tanstack/react-query';

// 4. Internal imports with aliases (alphabetical)
import { SignalCard } from '@/components/SignalCard';
import { usePortfolioData } from '@/hooks/usePortfolioData';
import { formatCurrency } from '@/lib/utils';

// 5. Types (always use 'import type' when importing only types)
import type { Signal } from '@/types/signals';
```

**Types and interfaces – architect-led standard**

The following reflects the **main architect** responsibility (see `.cursorrules`: think, evaluate, research first—do not blindly mirror existing code). Conventions here are based on research and critical evaluation; where the codebase diverges, the standard states the recommended direction.

**Architect evaluation (research first, then decide):**

Before locking in conventions, the main architect must research and evaluate—not just document “what the project does.” If the project’s choices conflict with current best practice, the standard must call that out and recommend a better path.

- **Research (2024–2026):** TypeScript community and enterprise guides (e.g. type-vs-interface 2025, OpenReplay “organize type definitions”, enterprise TS best practices) consistently say: (1) **Prefer `type` by default** for object shapes—closed, composable, no accidental declaration merging; reserve **`interface`** for class contracts, declaration merging, or framework extension. (2) **Organize by usage and domain**, not by keyword: inline → colocated (e.g. `*.types.ts`) → shared `src/types/`; one question—“how many files need this?”—drives placement. (3) **No widespread practice** of splitting “interfaces” into a separate folder from “types”; organization is by domain/scope, not by `interface` vs `type`.
- **Critical view of “we put everything in types/”:** A single “types” folder that mixes every kind of definition is fine only if we also (a) organize by domain inside it (`chart.ts`, `latency-stats.ts`, etc.) and (b) don’t dump hook-only shapes there. Our current structure (domain files under `@/types/`, co-located `types.ts` for hooks) aligns with that. What does **not** align with 2025 practice is using **`interface` for every object shape**; the recommended default is `type` for those, unless we need merging or `extends`.
- **Recommendation:** (1) **Location:** Keep a **unified `@/types/` by domain**; do **not** add a separate `interfaces/` folder—research shows organization by domain/usage, not by keyword. (2) **Keyword choice:** For **new** object shapes (props, API responses, DTOs), prefer **`type`** unless the codebase needs `interface` (e.g. class `implements`, declaration merging, or extending framework types). When touching existing files, migrate `interface` → `type` for plain object shapes where it’s low-risk. (3) **Placement rule:** Inline when single-file; colocated `types.ts` (or `*.types.ts`) when shared in a module; `@/types/<domain>.ts` when shared across features. This matches “place as close to usage as possible; promote only when needed.”

---

**When to use `interface` vs `type` (quick reference):**

| Use                                                        | Keyword     | When                                                                                        |
| ---------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------- |
| **Default for object shapes** (props, API responses, DTOs) | `type`      | Always, unless you need merging or `implements`.                                            |
| **Class contracts, library augmentation, `extends`**       | `interface` | When a class `implements` it, or you need declaration merging (e.g. extending React types). |
| **Unions, tuples, `typeof`, primitives**                   | `type`      | Only `type` supports these.                                                                 |

**Interfaces and types live together:** Do **not** put `interface` in a separate file or folder from `type`. In PulsAI, **both `interface` and `type` live in the same file or folder**—e.g. in `@/types/<domain>.ts` or in a co-located `types.ts` (e.g. `useFoo/types.ts`). We organize by **domain/usage**, not by keyword. No `@/interfaces/` folder and no `*.interfaces.ts`-only files.

**Types vs interfaces (TypeScript language):**

- **`interface`** – Object shape; supports declaration merging and `extends`. Use when you need mergeable or extendable contracts (e.g. class `implements`, library augmentation, `React.ComponentProps`).
- **`type`** – Type alias; unions, primitives, intersections, mapped types, object shapes. Use for string unions, tuples, `typeof`, and **for most object shapes** in modern TS (closed, composable, no accidental merging).

So: “types” (narrow) = `type` keyword; “interfaces” = `interface` keyword. They are different constructs. **Default for new object shapes in PulsAI: `type`.** Use `interface` only when the above reasons apply.

**Should we split “interfaces” and “types” into different folders?**

| Approach                                                              | Pros                                                                                                                               | Cons                                                                                | Architect view                                                                            |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| **Unified `@/types/` by domain** (both in same file, e.g. `chart.ts`) | One place per domain; “types” = all type-level definitions; fewer files; matches OpenReplay/enterprise “organize by usage/domain.” | Mixes keyword styles in one file.                                                   | **Recommended.** Aligns with research; no need to split by keyword.                       |
| **Separated `@/interfaces/` vs `@/types/`**                           | Clear keyword-based split.                                                                                                         | Same domain split across two modules; double imports; not standard in TS ecosystem. | **Not recommended.** Adds structure without benefit; conflicts with “organize by domain.” |
| **Suffix `*.interfaces.ts` vs `*.types.ts`**                          | Keyword separation per domain.                                                                                                     | Two files per domain; consumers often need both.                                    | **Not recommended.** Same as above.                                                       |

**Convention (location):** Inline when one file; **co-located `types.ts`** (or folder `Feature/types.ts`) when shared in a module; **`@/types/<domain>.ts`** when shared across features. Do **not** create a separate `interfaces/` folder or `*.interfaces.ts`; keep one file per domain under `@/types/` and put both `interface` and `type` there. For hooks with their own folder, use `useFoo/types.ts` for options/return and re-export domain types from `@/types/` where needed.

**Migration (interface → type):** For plain object shapes in `@/types/` (no class `implements`, no declaration merging), prefer `type Name = { ... }` over `interface Name`. Pilot completed: `@/types/latency-stats.ts` (LatencyStats), `@/types/signal-chart.ts` (SignalChartCandle, SignalChartSignal, SignalChartPrediction, SignalChartEquityPoint, SignalChartData). When touching other `@/types/*.ts` or co-located `types.ts` files, migrate object shapes to `type` where low-risk; keep `interface` only where extendability or merging is required.

**Audit (TanStack Query / data-layer migration code):**

| File / area                   | Types / interfaces                                             | Location (decision)                                                                                                              |
| ----------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `@/types/latency-stats.ts`    | `LatencyStats`                                                 | **Global `@/types/`** – domain shape shared by performance page, hook, fetcher.                                                  |
| `hooks/useLatencyStats/`      | `UseLatencyStatsOptions`, `UseLatencyStatsReturn`              | **Co-located `useLatencyStats/types.ts`** – hook-specific; re-exports `LatencyStats` from `@/types/latency-stats`.               |
| `hooks/useTrainingJob/`       | `UseTrainingJobReturn`                                         | **Co-located `useTrainingJob/types.ts`** – hook return shape; uses `TrainingJobItem` from `@/types/training-jobs`.               |
| `@/types/chart.ts`            | `OHLCVFetcherResult`                                           | **Global `@/types/`** – fetcher return shape shared by `fetchOHLCV` and `useOHLCVData`; uses `CandlestickData` and `VolumeData`. |
| `utils/ohlcv-api.ts`          | `BackendCandle`, `BackendOHLCVResponse`                        | **Inline in util** – API contract for OHLCV; single module.                                                                      |
| `services/api.ts`             | `AppFetchOptions`, `AuthErrorKey`                              | **Inline in service** – transport layer; single module.                                                                          |
| `SignalChartSection/types.ts` | `SignalChartSectionProps`, etc.                                | **Co-located** – already present; organism-specific.                                                                             |
| `@/types/signal-chart.ts`     | `SignalChartData`, …                                           | **Global `@/types/`** – shared by chart components and fetchers.                                                                 |
| `@/types/signals-list.ts`     | `SignalsListItem`, `SignalsListFilters`, `SignalsListResponse` | **Global `@/types/`** – list API shape shared by fetchSignalsList, useSignals, dashboard signals page.                           |
| `@/types/latest-signal.ts`    | `LatestSignalResult`                                           | **Global `@/types/`** – GET /signals/{symbol} result shape shared by fetchLatestSignal and useLatestSignal.                      |

When adding new hooks under Phase 7+: put **domain types** (e.g. response shapes used by multiple features) in **`@/types/<domain>.ts`**; put **hook options/return** in a co-located **`<hookName>/types.ts`** if the hook gets a folder, or keep them in the hook file if there are only one or two.

**Do not define shared types in `config/queryFetchers.ts`.** Fetchers only import types from `@/types/` (or utils when module-scoped). Any type used by both the fetcher and a hook/page belongs in `@/types/<domain>.ts`.

**Python (Backend) - Import Order:**

```python
# 1. Standard library
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated

# 2. Third-party
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local application imports (use absolute imports)
from src.infrastructure.database import get_db
from src.domain.models import User, Signal
from src.application.services import SignalService
```

**HTTP status codes (FastAPI / Starlette) — single source of truth**

- **Routes, dependencies, middleware, and any code that returns an HTTP status** (including `JSONResponse(status_code=...)`) should use **`from fastapi import status`** and **`status.HTTP_*`** (e.g. `status.HTTP_400_BAD_REQUEST`, `status.HTTP_413_CONTENT_TOO_LARGE`). That matches Starlette/FastAPI’s canonical names and avoids magic numbers.
- **`src/infrastructure/exceptions.py`** `HTTP_*` constants are the **domain exception hub** and **error_handler log classification** (e.g. treating 4xx vs 5xx, mapping to log levels). **Do not** duplicate every RFC status code there—**do not** maintain two parallel lists of numeric codes.
  - Middleware and transport-layer responses → **`fastapi.status`**.
  - `PulsAIException` subclasses and shared thresholds → **`infrastructure.exceptions`** where already defined.

---

## 8. Performance Requirements

### 8.1 Latency Budgets (CRITICAL for Trading)

```yaml
Critical Paths:
  Signal Generation: < 50ms
    - 50ms delay on BTC can mean $100+ price change
    - MUST be optimized

  Trade Execution: < 100ms
    - From signal to exchange API call
    - Includes validation, risk checks

  API Response: < 200ms
    - User-facing endpoints
    - p95 latency target

Non-Critical Paths:
  Backtest Execution: < 30 seconds per 1000 trades
  Model Training: < 10 minutes
  Report Generation: < 5 seconds
```

### 8.2 Performance Monitoring

```python
import time
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec('P')
T = TypeVar('T')

def measure_latency(threshold_ms: float = 50.0) -> Callable:
    """Decorator to measure and alert on function latency."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                if elapsed_ms > threshold_ms:
                    logger.warning(
                        f"SLOW: {func.__name__} took {elapsed_ms:.2f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )
                metrics.histogram(
                    f"function.latency.{func.__name__}",
                    elapsed_ms,
                )
        return wrapper
    return decorator

# Usage
@measure_latency(threshold_ms=50.0)
async def generate_signal(symbol: str) -> Signal:
    """Generate trading signal - MUST complete in < 50ms."""
    ...
```

### 8.3 Numba JIT: Loop Variable Names (Backend)

When writing `@njit` or Numba-jitted functions, use **distinct loop variable names** for each loop in the same function. Reusing the same name (e.g. `i` in multiple sequential `for` loops) violates Numba’s SSA (Static Single Assignment) form; the compiler will “fix” it and may emit DEBUG logs when root log level is DEBUG. Behavior tests won’t catch this (output is correct); avoid it via style.

```python
# BAD - same name `i` in multiple loops causes SSA violator
for i in range(slope_period, n):
    obv_slope[i] = (obv[i] - obv[i - slope_period]) / slope_period
for i in range(slope_period, n):  # reuse of `i`
    start = max(slope_period, i - norm_window + 1)
    ...

# GOOD - distinct names
for idx in range(slope_period, n):
    obv_slope[idx] = (obv[idx] - obv[idx - slope_period]) / slope_period
for k in range(slope_period, n):
    start = max(slope_period, k - norm_window + 1)
    ...
```

See TESTING_STRATEGY.md § “Numba JIT / SSA violator” for why this isn’t covered by behavior tests.

### 8.4 Request-path model loading (Backend — SoT)

**Rule:** In the **HTTP request path** (any code that runs when FastAPI is handling an incoming HTTP request—routes, dependencies, and use cases they call), model loading must **not** call sync `storage.load()` or `storage.load_production()`. Use **only** `storage.load_async()` / `storage.load_production_async()` so the single event loop is not blocked by `joblib.load` and can keep serving other requests.

- **SoT:** `ModelStorage.load_async` and `load_production_async` are the single way to load models in that path; they run sync I/O in a dedicated `_model_load_executor` thread pool.
- **Why “request path” only:** In the API process, one event loop serves all HTTP requests. If a route blocks it with sync `joblib.load`, every other request (signals, health, other users) stalls. So we forbid sync load there.
- **Other contexts (allowed to use sync load):** Code that does **not** run inside the FastAPI request path is out of scope for this rule:
  - **Celery workers:** Run in separate processes. There is no FastAPI app and no shared event loop; only that task runs. Blocking on `storage.load()` blocks only that worker process, not other users’ requests. So sync `storage.load()` / `storage.load_production()` is allowed there (e.g. `RetrainingTriggerService`, training tasks).
  - **API lifespan and Celery `worker_process_init`:** Startup hooks that call `GenerateSignalUseCase._get_models` to fill the in-process cache are **not** the HTTP request path. @see `application/services/signal_model_prewarm.py`, `main._prewarm_model_cache`, `celery_app.prewarm_worker_pool_child`.
  - **Sync scripts (CLI, one-off jobs):** No web server, no concurrent requests. Blocking on disk is acceptable.
- **Where the rule applies:** Admin routes (models, arena, backtest hub), `SubmitEnsembleTrainingJobsUseCase`, `BacktestExecutionService` when invoked from the API (e.g. `execute_prefetched`).

@see BACKEND_ARCHITECT_AUDIT.md §9.1.

### 8.5 Live signal feature set (Backend)

**Rule:** For live ML signal generation, the feature set to compute is determined at runtime from the **primary** (first) production model’s metadata: `primary.metadata.feature_columns` plus `CHART_MARKER_COLUMNS`. Use `calculate_selected(ohlcv, columns_to_compute)`, not `calculate_all`, so only the needed columns are computed (latency target &lt; 20 ms).

- One feature set per (symbol, timeframe), defined by the primary model. All production models for that pair must be trained on the same feature set (ensemble receives one shared X).
- **Multiple timeframes:** Each (symbol, timeframe) is a separate invocation with its own OHLCV, calculator config, and models; no cross-TF feature mix in one request.
- **Edge cases:** Empty or mismatched `feature_columns`, missing columns in codebase, and ensemble models with different feature sets need explicit handling in code and tests.

### 8.6 ML Numeric Precision (Backend — SoT)

**Rule:** In any ML prediction or decision pipeline, **never downcast floating-point
values** from `float64` to `float32` (or lower) when the value will be compared
against a threshold, used for ranking, or returned as a confidence/probability.

This applies to **all** model types: XGBoost, LSTM, GRU, BiDirectional, RL,
ensembles, and any future architecture.

**Why:**

`float32` has ~7 significant digits; `float64` has ~15. When a probability like
`0.499999970197` (below 50% threshold → HOLD) is cast to `float32`, it rounds
to `0.5` (at threshold → BUY). One bit of precision flips a trading decision.

This exact bug was found in production — see
[POSTMORTEM_LOOKAHEAD_BIAS_2026_04_14.md](../02-technical/POSTMORTEM_LOOKAHEAD_BIAS_2026_04_14.md)
§4 for the full analysis.

**Mandatory precision rules:**

| Context                                              | Required dtype                | Rationale                                               |
| ---------------------------------------------------- | ----------------------------- | ------------------------------------------------------- |
| `predict_proba` output before threshold comparison   | `float64`                     | Threshold comparison is a binary decision; 1e-7 matters |
| Confidence values stored in DB / returned via API    | `float64`                     | Reproducibility of threshold decisions on replay        |
| Feature matrix passed to model                       | `float64` (or model's native) | Avoid silent truncation of indicator precision          |
| Threshold constants (`min_confidence`, `min_sharpe`) | `float64` (Python `float`)    | Default; never narrow to match a downcast operand       |
| Intermediate rolling statistics (mean, std, etc.)    | `float64`                     | Cumulative rounding in rolling windows compounds        |

**Forbidden patterns:**

```python
# BAD — downcasts before threshold comparison
confidences = probabilities[idx, preds].astype(np.float32)
if confidences[i] >= min_confidence:  # float32 vs float64 → precision flip
    ...

# BAD — downcasts for "efficiency" in decision path
features = feature_matrix.astype(np.float32)  # silent precision loss
predictions = model.predict_proba(features)

# BAD — mixing dtypes across pipeline stages
proba_f32 = model.predict_proba(X).astype(np.float32)  # stage 1
action = "BUY" if proba_f32[0] >= 0.5 else "HOLD"     # stage 2: float64 threshold
```

**Allowed patterns:**

```python
# OK — float32 for model INTERNAL weights (training, GPU memory)
model = LSTMModel(dtype=torch.float32)  # internal weights

# OK — float32 for storage/serialization IF re-promoted before comparison
saved = confidences.astype(np.float32)     # storage
loaded = saved.astype(np.float64)          # re-promote BEFORE any comparison
if loaded[i] >= min_confidence: ...        # safe

# OK — float64 throughout the decision path (default, preferred)
confidences = probabilities[idx, preds].astype(np.float64)
if confidences[i] >= min_confidence: ...   # both float64
```

**Enforcement:**

- Automated test in `test_ml_precision_guardrail.py` scans ALL prediction
  functions for `float32` downcasts in the confidence/threshold path.
- Code review: any `.astype(np.float32)` or `.astype("float32")` in
  `ml_inference_pipeline.py`, `backtest_predictions.py`, or any new model
  pipeline file **must be justified in a code comment** explaining why
  precision loss is acceptable at that point.

@see [POSTMORTEM_LOOKAHEAD_BIAS_2026_04_14.md](../02-technical/POSTMORTEM_LOOKAHEAD_BIAS_2026_04_14.md) §4.

---

## 9. Code Review Checklist

Before ANY code is merged, verify:

```markdown
## Functionality

- [ ] Code does what it's supposed to do
- [ ] Edge cases are handled
- [ ] Error handling is complete

## Architecture

- [ ] Follows SRP (Single Responsibility)
- [ ] No DRY violations
- [ ] Depends on abstractions (DIP)
- [ ] Can be extended without modification (OCP)

## Code Quality

- [ ] No ternary operators for complex logic
- [ ] Uses guard clauses / early returns
- [ ] Meaningful variable and function names
- [ ] Type hints (Python) / strict types (TypeScript)
- [ ] Documentation for public APIs

## Testing

- [ ] Unit tests for all public methods
- [ ] Tests cover edge cases
- [ ] Tests are fast (< 100ms per test)
- [ ] Coverage meets repo gates (≥80% backend, ≥90% frontend); see `docs/05-testing/COVERAGE_REQUIREMENTS.md`

## Performance

- [ ] No N+1 queries
- [ ] Critical paths < 50ms
- [ ] No blocking I/O in async code

## Security

- [ ] No hardcoded secrets
- [ ] Input validation on all user inputs
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding)
```

### 9.1 PR checklist (required — aligns with PULL_REQUEST_TEMPLATE)

Every pull request MUST satisfy the following. These items are reflected in [.github/PULL_REQUEST_TEMPLATE.md](../../.github/PULL_REQUEST_TEMPLATE.md); the checklist there must be completed before merge.

- **No inline styles** — Use Tailwind / CSS modules; no `style={{ }}` for layout or theme. **Exception:** A single dynamic value (e.g. `style={{ height }}` or `style={{ width: \`${percentage}%\` }}`) is allowed when the value is data-driven and cannot be expressed with Tailwind arbitrary values (e.g. to avoid purge/safelist issues). Prefer CSS variables or data attributes where practical.
- **No inline types and/or interfaces** — Hook/component types live in co-located `types.ts` or `@/types/<domain>.ts`; not defined in the same file as the component/hook implementation. Exception: **small types** (e.g. a single prop type or a two-line interface) are allowed **only when no more than 2** are inline in the same file; otherwise move to co-located `types.ts` or `@/types/`.
- **No inline configuration** — Option arrays, dropdown configs, and form constants (e.g. `MAX_POSITIONS_OPTIONS`, `SIGNAL_SOURCE_OPTIONS`, `CLASSIC_SIGNAL_OPTIONS`) must live in co-located `constants.ts` or `config.ts`, or in `@/config/` / `@/utils/constants`. No large inline arrays or config objects in component files; single source of truth, testable in isolation.
- **No inline components** — UI subcomponents (e.g. `SignalSourceSelector`, `ConfidenceSlider`) must be decoupled: extracted to their own file under the same feature folder (or to atoms/molecules when reusable). Inline components cannot be unit-tested in isolation; extract and add tests when behavior matters.
- **Optimization (useMemo, useCallback, memo)** — Spot bottlenecks: wrap expensive derivations in `useMemo`, event handlers passed to children in `useCallback`, and pure list/item or leaf components in `React.memo` when re-renders are costly. Avoid premature optimization; apply where props are stable and parent re-renders often.
- **Following and correcting linters** — No warnings; complexity and unused vars fixed; lint run and passing.
- **Files maintained under ~400 lines** — TS/JS general cap 400; page components (`page.tsx`) under ~600; Python 400 EFFECTIVE lines (imports, the `TYPE_CHECKING` block and the module docstring do not count) with 500 as the hard ceiling past which a file owes a split; functions under 100 lines (split into smaller components/hooks/utils if over).
- **No God providers/hooks/services** — Providers must stay orchestration-only. Move context definitions, inline types, storage logic, event subscriptions, formatting helpers, and API orchestration into co-located modules/hooks with isolated unit tests.
- **Path aliases** — ALWAYS use `@/` path aliases from tsconfig (`@/hooks/`, `@/components/`, `@/types/`, etc.) for EVERY `src/` import, including same-folder siblings. NEVER use a relative import (`./` or `../`) in `src/`. Enforced by `pulsai-fe-imports/prefer-alias-imports` (error + auto-fix).
- **Reusable components (if any)** — Do not reinvent the wheel; reuse existing hooks, utils, helpers, atoms/molecules/organisms where applicable; or extract/extend new reusable pieces where it makes sense.
- **Verification commands run** — Frontend: `cd apps/web && pnpm verify`. Backend: `./scripts/verify.sh`. All pass before opening PR.
- **Tests** — Added/updated; behavior-focused (outcomes), not implementation-only; coverage meets repo gates (`COVERAGE_REQUIREMENTS.md`).
- **No debug or dead code** — No `console.log`/debug in prod (or gated for dev); no dead imports, unused vars, or commented-out blocks; linters/IDE clean.
- **Cleanup on unmount (React/RN)** — Event listeners, subscriptions, and timers unregistered in `useEffect` cleanup; no memory leaks.
- **Accessibility (if UI)** — Descriptive labels/alt text, keyboard reachable, focus indicators, semantic HTML/ARIA where needed; contrast and heading order considered.
- **Async/loading and errors** — Loading states for async work; error handling and user-facing messages are specific and actionable.
- **Self-review** — Diff reviewed line-by-line; no obvious bugs, dead code, or security issues; docs/README updated if behavior or setup changed.

---

## 10. Enforcement

These standards are enforced via:

1. **Pre-commit hooks**: Linting, formatting, type checking
2. **CI/CD pipeline**: Tests, coverage checks
3. **Code review**: Manual verification
4. **Automated tools**:
   - Python: `ruff` (lint/format), `mypy` (CI + verify step 1 — must pass), `basedpyright` (verify step **2i** + CI ratchet — **`apps/api/src` only**; catches unused symbols / return-path gaps mypy misses; full verify = corpus baseline `BASEDPYRIGHT_ERROR_BASELINE` in `apps/api/scripts/verify.sh`; `--fast` = touch-gate on changed `src/` files, zero errors required). IDE type underlines for `src/` usually come from basedpyright/`pyrightconfig.json`, not from mypy.
   - **`src/research` typing policy (SoT):** not under basedpyright’s blocking gate. Default ruff/mypy **exclude** research in `pyproject.toml`; `verify.sh` re-includes a **subset**: step **2j** (ruff bug-class ratchet) + step **2k** (mypy crash-class ratchet). `pyrightconfig.json` **excludes** `apps/api/src/research` so IDE underlines match that policy (measured: SoT research files are dominated by pandas stub noise under basedpyright, not the dual-checker value seen on `src/`).
   - TypeScript: `eslint`, `prettier`, `tsc --strict`, `knip`

No exceptions. No "I'll fix it later."

### 10.1 Knip — dead-code & dependency-hygiene gate (`apps/web`)

`knip` complements ESLint + `tsc` by catching cross-file dead code that the linter and compiler cannot see: unused files, unused exports, unused `package.json` dependencies, unresolved imports, and unlisted dependencies. It backstops manual dead-code purges (e.g. [PAPER_VESTIGES_AUDIT.md](./PAPER_VESTIGES_AUDIT.md)) so the same drift cannot recur silently.

**Gate split** (config: [apps/web/knip.config.ts](../../apps/web/knip.config.ts)):

| Script             | Scope                                                                 | Status                 | Trigger                                                                                                                                                                                                                              |
| ------------------ | --------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `pnpm knip:strict` | `dependencies`, `unlisted`, `unresolved`, `files`, `exports`, `types` | **Blocks push and CI** | Pre-push scoped to `apps/web/**/*.{ts,tsx,mts,mjs,json}` (see [pre-push-policy.sh](../../scripts/pre-push-policy.sh) `PRE_PUSH_WEB_KNIP_PATTERN`); GitHub Actions `frontend-lint` job (see [ci.yml](../../.github/workflows/ci.yml)) |
| `pnpm knip`        | Full report (same scope; left non-blocking for ad-hoc inspection)     | Advisory               | Manual / periodic                                                                                                                                                                                                                    |

**Closed state (Slice 2 / 3a / 3b shipped):** all six Knip categories are now blocking. Any new dead dep, unused file, unused export, or unused type fails pre-push and CI. The historical backlog of 1,340 advisory items was scrubbed across 4 commits (Slice 1, 1b, 3a, 3b + Slice 2), with cascade-orphaned barrels deleted in the same commits that exposed them.

**Backlog history (locked):**

| Category       | At gate intro | Slice 1 (-14) | Slice 1b (-11) | Slice 3a (-302) | Slice 3b (-478) | Slice 2 (-533) | Status                       |
| -------------- | ------------- | ------------- | -------------- | --------------- | --------------- | -------------- | ---------------------------- |
| Unused files   | 25            | 11            | **0**          | 0               | 0               | 0              | Blocking since Slice 1b      |
| Unused types   | 782           | 782           | 782            | 478             | **0**           | 0              | Blocking since Slice 3b      |
| Unused exports | 533           | 533           | 533            | 533             | 533             | **0**          | Blocking since Slice 2 (now) |

**Scrub tool: [`apps/web/scripts/knip-scrub.mjs`](../../apps/web/scripts/knip-scrub.mjs)**. AST-based scrubber using TypeScript's compiler API. Operates on real AST nodes (no regex on TS source), iterates `tsc` cascade until clean (TS6196 / TS6133 / TS6192 orphan deletion), coalesces overlapping edit ranges before applying. Re-runnable on any future drift if categories regress.

**Slice 1b note (barrel cleanup):** The 11 `<dir>/index.ts` barrels left after Slice 1 had zero direct consumers — every reachable export was already imported via the source file directly (`@/components/atoms/Logo/Logo`, not `@/components/atoms/Logo`). The barrels were dead wrappers and were deleted. PulsAI does NOT enforce barrel-only imports anywhere (no ESLint `no-restricted-imports` ban on deep paths); if barrel-style imports become a structural preference in the future, that would be a separate, dedicated slice (call it "Slice X — barrel SoT").

**False-positive policy:** before adding to `ignoreDependencies`, prove the dep is actually used (rule-name reference, CLI binary via `spawn`, transitive plugin loaded by another tool). Don't ignore a dep just to silence the gate.

**Re-run locally:** `cd apps/web && pnpm knip:strict` (must exit 0).

---

## 11. Ruff Configuration (Python Linter)

### 11.1 Global Ignore Rules

The rules globally ignored in `apps/api/pyproject.toml` -- `[tool.ruff.lint] ignore`, which is the source of
truth, each with its measured reason beside it. `tests/unit/architecture/test_coding_standards_global_ignores.py`
reads this table AND that list and fails when they differ, so this copy cannot drift again (it did: until
2026-10-12 it listed three rules un-ignored on 2026-08-07 and omitted eleven real ones).

| Rule        | Description                       | Reason                                                                                                                         |
| ----------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `ANN401`    | Allow `Any` type                  | Owned by the explicit-Any ratchet (§5.1), which counts every `Any` and may only fall                                           |
| `S101`      | Allow `assert`                    | Tests and runtime invariant checks                                                                                             |
| `S105/S106` | Allow hardcoded test passwords    | Test fixtures only                                                                                                             |
| `S603`      | `subprocess` without `shell=True` | Fires on every call; the measured sites launch our own interpreter with a literal argv (`S602` / `S605` stay on)               |
| `TRY003`    | Long messages in `raise`          | Opinionated; the error messages are deliberately descriptive                                                                   |
| `TRY300`    | `try` / consider `else`           | Style, not a bug                                                                                                               |
| `TRY301`    | `raise` within `try`              | Validation raises inside `try` blocks (FastAPI handlers, Celery control flow)                                                  |
| `TRY401`    | Verbose log message               | Verbose error logs are wanted in a trading platform                                                                            |
| `PLW2901`   | Loop variable overwritten         | Common in data pipelines                                                                                                       |
| `PLC0415`   | Import outside top level          | Lazy imports: circular-dependency breaks, heavy ML libraries deferred                                                          |
| `PLW0603`   | `global` statement                | Module-level singletons; the `global-statement` standards rule (STANDARDS_GATE_MAP.md) makes a touched file pay its count down |
| `PLW0108`   | `lambda` in an ORM default        | SQLAlchemy expects a nullary callable                                                                                          |
| `TC003`     | stdlib imports used at runtime    | Pydantic / SQLAlchemy resolve them at runtime                                                                                  |
| `UP040`     | `X: TypeAlias` -> `type X = ...`  | `type` builds a `TypeAliasType`, which changes pydantic behaviour (measured; see the pyproject note)                           |

`RUF012`, `SIM102` and `PTH123` were un-ignored on 2026-08-07 after their findings in `src/` were fixed (§11.3).

### 11.2 Per-File Ignore Rules

**ML Files** (`src/infrastructure/ml/`, `src/application/use_cases/generate_signal.py`, `src/domain/services/features/`, `src/scripts/`):

| Rule          | Description             | Reason                                                 |
| ------------- | ----------------------- | ------------------------------------------------------ |
| `N806`        | Uppercase variables     | ML convention: `X`, `y`, `X_train`, `X_test`           |
| `N803`        | Uppercase arguments     | ML convention: function args like `X`                  |
| `TC002/TC003` | Type-checking imports   | `numpy`/`polars` used at runtime for data manipulation |
| `ERA001`      | Commented-out code      | Section headers in feature lists (documentation)       |
| `ANN001`      | Missing type annotation | Dynamic model types from registry pattern              |
| `ARG002`      | Unused arguments        | Future-proofing in training methods                    |
| `E501`        | Line too long           | Complex ML one-liners (metrics, etc.)                  |

**Test Files** (`tests/**/*.py`):

| Rule        | Description          | Reason                                  |
| ----------- | -------------------- | --------------------------------------- |
| `S101`      | Allow `assert`       | Testing framework requirement           |
| `ANN`       | All annotation rules | Relaxed type hints in tests             |
| `ARG`       | Unused arguments     | Fixture arguments may appear unused     |
| `N806/N803` | Uppercase variables  | Mock naming: `MockStorage`, `MockModel` |
| `E501`      | Line too long        | Long assertion messages                 |
| `ERA001`    | Commented-out code   | Expected value documentation            |

### 11.3 Tech Debt Tracker

Items marked for future cleanup:

```markdown
## Tech Debt: Ruff Rules (Priority: LOW)

- [x] **RUF012** (was 9 sites): Add `ClassVar` annotations to mutable class attributes
      Files: ohlcv_fetcher.py (3, incl. the derived `CONNECTABLE_EXCHANGES`), csrf.py (2),
      ohlcv_cache.py, demo_trading_model.py (`__mapper_args__`), classic_signal_generator.py,
      lookahead_detector.py, admin_indicator_inventory_correlation_service.py
      DONE 2026-08-07 — `ruff check src --select RUF012` = 0

- [x] **PTH123** (was 9 sites): Replace `open()` with `Path.open()`
      Files: ml_config.py (2), storage_backends/local.py, chart_ohlcv.py, chart_json.py,
      chart_backtest.py, sources_loader.py, train_model_persistence.py,
      migrate_storage_layout.py
      DONE 2026-08-07 — `ruff check src --select PTH123` = 0

- [x] **SIM102**: Simplify nested if statements where appropriate
      Files: ohlcv_cache.py (+ 12 other src sites cleared 2026-08-07)
      DONE — `ruff check src --select SIM102` = 0
```

**All three are now UN-IGNORED** in `pyproject.toml` (`[tool.ruff.lint] ignore`), so they fail
the build if they come back. They remain relaxed for `tests/**` and `scripts/**` via
`per-file-ignores`: `open()` is idiomatic in a fixture, and the 43 remaining PTH123 sites there
buy no production safety.

> **Why the un-ignore matters more than the fixes.** These sat as global ignores labelled
> "TECH DEBT" and drifted: the list above previously named `model_storage.py` for PTH123 (it has
> had none for some time) and 2 files for RUF012 where 7 carried it. Re-measured 2026-08-07 with
> `ruff check src --select RUF012,PTH123,SIM102 --statistics`. A global ignore is not debt
> tracking, it is debt hiding — nothing was enforcing the checklist, so the checklist rotted.
> Prefer `per-file-ignores` with a stated reason over a global ignore with a "TECH DEBT" comment.

### 11.4 Adding New Rules

When adding new ignore rules:

1. **Document the reason** in `pyproject.toml` with comments
2. **Update this section** with the rule and justification
3. **Create tech debt ticket** if it's a temporary workaround
4. **Prefer per-file ignores** over global ignores when possible

---

## 12. Constants and Magic Numbers

### 12.1 Overview

Magic numbers and strings scattered across the codebase are a code smell. They:

- Are hard to find and change
- Lack context (what does `0.02` mean?)
- Lead to inconsistencies (different values in different files)
- Can't leverage TypeScript's type system

### 12.2 When to Centralize vs. Keep Inline

| Constant Type               | Centralize? | Example                                 | Location               |
| --------------------------- | ----------- | --------------------------------------- | ---------------------- |
| **Business logic values**   | ✅ YES      | Initial capital, risk percentages       | `@/utils/constants.ts` |
| **Status/enum-like values** | ✅ YES      | `'BUY'`, `'SELL'`, `'pending'`          | `@/utils/constants.ts` |
| **API contract values**     | ✅ YES      | Status codes from backend               | `@/utils/constants.ts` |
| **Configuration defaults**  | ✅ YES      | Pagination size, timeouts               | `@/utils/constants.ts` |
| **UI/styling values**       | ❌ NO       | `rounded-lg`, `opacity-50`, `z-10`      | Inline in component    |
| **Array indices**           | ❌ NO       | `data[0]`, `items.slice(0, 5)`          | Inline                 |
| **One-off values**          | ❌ NO       | `setTimeout(fn, 300)`                   | Inline                 |
| **Loop boundaries**         | ❌ NO       | `i < 10`, `for (let i = 0; i < 3; i++)` | Inline                 |

### 12.3 Constants File Pattern

```typescript
// @/utils/constants.ts

/**
 * Trading signal actions.
 *
 * WHY these values:
 * - BUY: Enter long position
 * - SELL: Exit position or enter short
 * - HOLD: No action, maintain current state
 */
export const SIGNAL_ACTIONS = {
  BUY: 'BUY',
  SELL: 'SELL',
  HOLD: 'HOLD',
} as const;

// Derive type from const object (no runtime overhead)
export type SignalAction = (typeof SIGNAL_ACTIONS)[keyof typeof SIGNAL_ACTIONS];

/**
 * Default values for backtest configuration.
 *
 * WHY centralized:
 * - Used in multiple components (form, display, API calls)
 * - Business logic values that may change
 * - Type-safe with autocomplete
 */
export const BACKTEST_DEFAULTS = {
  INITIAL_CAPITAL: 10000,
  HOLDING_PERIODS: 4,
  MIN_CONFIDENCE: 50,
  MAX_POSITIONS: 1,
  RISK_REWARD_RATIO: 2.0,
} as const;
```

### 12.4 Usage Examples

```typescript
// ✅ GOOD - Business logic from constants
import { BACKTEST_DEFAULTS, SIGNAL_ACTIONS } from '@/utils/constants';

const initialCapital = BACKTEST_DEFAULTS.INITIAL_CAPITAL;
const action = SIGNAL_ACTIONS.BUY;

// ✅ GOOD - UI values inline (not business logic)
<div className="rounded-lg opacity-50 p-4">
  {items.slice(0, 5).map(item => ...)}
</div>

// ❌ BAD - Business logic hardcoded
const initialCapital = 10000; // Magic number! What if this changes?
const action = 'BUY'; // Magic string! Typo-prone

// ❌ BAD - Over-centralized (UI values don't belong in constants)
const UI_OPACITY = 0.5; // This is overkill
const UI_PADDING = 4;   // Just use Tailwind classes
```

### 12.5 Why `as const` Over TypeScript Enums

```typescript
// ❌ AVOID - TypeScript enum (compiles to runtime object)
enum SignalAction {
  BUY = 'BUY',
  SELL = 'SELL',
  HOLD = 'HOLD',
}
// Compiles to ~150 bytes of runtime JavaScript

// ✅ PREFER - const object (zero runtime overhead)
export const SIGNAL_ACTIONS = {
  BUY: 'BUY',
  SELL: 'SELL',
  HOLD: 'HOLD',
} as const;
// Compiles to nothing - just type information
```

**Benefits of `as const`:**

- **Zero bundle size** - Erased at compile time
- **Tree-shakeable** - Unused values don't ship
- **Works with API** - String values work naturally with JSON
- **Full type inference** - IDE autocomplete works perfectly

### 12.6 ESLint Enforcement

The `@typescript-eslint/no-magic-numbers` rule warns on suspicious numeric literals:

```javascript
// eslint.config.mjs
'@typescript-eslint/no-magic-numbers': [
  'warn',
  {
    ignore: [0, 1, -1, 2, 3, 4, 5, 10, 12, 24, 60, 100, 1000, 0.5, 0.25, 0.75],
    ignoreArrayIndexes: true,
    ignoreDefaultValues: true,
    ignoreEnums: true,
    ignoreNumericLiteralTypes: true,
    ignoreReadonlyClassProperties: true,
    ignoreTypeIndexes: true,
  },
],
```

**WARN, and it still blocks**: `pnpm lint` and lint-staged run `eslint --max-warnings=0`, so a warning fails the gate exactly like an error -- the level only changes how the editor shows it. React / Next.js layout numbers are why the rule is scoped the way it is, not why it is soft: it is not soft.

### 12.7 Code Review Guidelines

During code review, ask:

1. **Is this a business value?** → Centralize in `constants.ts`
2. **Is this used in multiple files?** → Centralize
3. **Would changing this require finding all occurrences?** → Centralize
4. **Is this just UI/styling?** → Keep inline
5. **Is this self-explanatory in context?** → May be okay inline

```typescript
// Review question: "What is 0.02?"
const riskAmount = balance * 0.02; // ❌ Magic number - centralize!

// Better:
const riskAmount = balance * RISK_DEFAULTS.PER_TRADE; // ✅ Self-documenting
```

---

## 13. Accessibility (WCAG Compliance)

> **Accessibility gaps are BUGS, not features.** Missing ARIA attributes, keyboard support,
> and screen reader compatibility violate WCAG 2.1 guidelines and are legal requirements
> in many jurisdictions.

### 13.1 Modal/Dialog Requirements (MANDATORY)

Every modal/dialog component MUST have these accessibility features:

```typescript
// ✅ GOOD - Fully accessible modal
function AccessibleModal({ isOpen, onClose, title, children }) {
  const modalRef = useRef<HTMLDivElement>(null);

  // 1. ESC key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      modalRef.current?.focus(); // Focus modal on open
    }

    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"                    // 2. Dialog role
      aria-modal="true"                // 3. Mark background as inert
      aria-labelledby="modal-title"    // 4. Link to title
    >
      <div ref={modalRef} tabIndex={-1}>
        <h2 id="modal-title">{title}</h2>
        <button
          onClick={onClose}
          aria-label="Close"            // 5. Accessible name for icon button
        >
          ✕
        </button>
        {children}
      </div>
    </div>
  );
}

// ❌ BAD - Inaccessible modal (DO NOT DO THIS)
function InaccessibleModal({ isOpen, onClose, children }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose}>✕</button>  {/* No aria-label! */}
        {children}
      </div>
    </div>
  );
}
```

### 13.2 Modal Checklist

| Requirement               | WCAG  | Description                       |
| ------------------------- | ----- | --------------------------------- |
| `role="dialog"`           | 4.1.2 | Screen readers announce as dialog |
| `aria-modal="true"`       | 2.4.3 | Marks background content as inert |
| `aria-labelledby`         | 4.1.2 | Links to visible title element    |
| ESC key closes            | 2.1.1 | Keyboard users can close modal    |
| Focus on open             | 2.4.3 | Focus moves into modal            |
| Focus trap                | 2.4.3 | Tab cycles within modal only      |
| Close button `aria-label` | 4.1.2 | Icon buttons need accessible name |

### 13.3 Button/Interactive Element Requirements

```typescript
// ✅ GOOD - Accessible icon button
<button onClick={onAction} aria-label="Delete item">
  <TrashIcon />
</button>

// ✅ GOOD - Button with visible text (no aria-label needed)
<button onClick={onAction}>
  <TrashIcon /> Delete
</button>

// ❌ BAD - Icon-only button without aria-label
<button onClick={onAction}>
  ✕
</button>

// ❌ BAD - Div with click handler (not keyboard accessible)
<div onClick={onAction}>Click me</div>

// ✅ GOOD - If you must use div, add role and keyboard support
<div
  role="button"
  tabIndex={0}
  onClick={onAction}
  onKeyDown={(e) => e.key === 'Enter' && onAction()}
>
  Click me
</div>
```

### 13.4 Form Input Requirements

```typescript
// ✅ GOOD - Input with associated label
<label htmlFor="email">Email</label>
<input id="email" type="email" aria-describedby="email-error" />
{error && <span id="email-error" role="alert">{error}</span>}

// ✅ GOOD - Input with aria-label (when visual label not possible)
<input type="search" aria-label="Search users" placeholder="Search..." />

// ❌ BAD - Input without any label
<input type="email" placeholder="Email" />
```

### 13.5 Color Contrast & Visual Indicators

```typescript
// ❌ BAD - Color-only indication
<span className={isError ? 'text-red-500' : 'text-green-500'}>
  {status}
</span>

// ✅ GOOD - Color + icon/text indicator
<span className={isError ? 'text-red-500' : 'text-green-500'}>
  {isError ? '❌' : '✅'} {status}
</span>
```

### 13.6 WCAG Violations Audit (2026-02-03)

**Current violations to fix:**

| File                                  | Issue                             | Severity | Fix                      |
| ------------------------------------- | --------------------------------- | -------- | ------------------------ |
| `admin/audit/page.tsx` (DetailsModal) | Missing `role="dialog"`           | Critical | Add attribute            |
| `admin/audit/page.tsx` (DetailsModal) | Missing `aria-modal="true"`       | Critical | Add attribute            |
| `admin/audit/page.tsx` (DetailsModal) | Missing ESC key handler           | Critical | Add event listener       |
| `admin/audit/page.tsx` (DetailsModal) | Close button missing `aria-label` | High     | Add `aria-label="Close"` |
| `admin/audit/page.tsx` (DetailsModal) | No focus management               | Medium   | Add ref + tabIndex       |

**Compliant components (reference implementations):**

- `ConfirmModal` - Full accessibility
- `FeatureExclusionModal` - Full accessibility
- `AnalyzeChartButton` panel - Full accessibility

### 13.7 Testing Accessibility

**Manual testing checklist:**

```markdown
- [ ] Can navigate with keyboard only (Tab, Shift+Tab, Enter, Escape)
- [ ] Focus visible on all interactive elements
- [ ] Modal traps focus correctly
- [ ] Screen reader announces dialog/button names correctly
- [ ] Color is not the only indicator of state
- [ ] Text contrast ratio >= 4.5:1 (WCAG AA)
```

**Automated tools:**

- Browser DevTools Lighthouse (Accessibility audit)
- eslint-plugin-jsx-a11y (compile-time checks)
- @axe-core/react (runtime checks in dev)

### 13.8 ESLint A11y Rules

The `jsx-a11y` plugin is included via `eslint-config-next`. We configure explicit rules in `eslint.config.mjs`:

**Critical Rules (ERROR - blocks CI):**

| Rule                           | Purpose                          |
| ------------------------------ | -------------------------------- |
| `alt-text`                     | Images must have alt text        |
| `anchor-has-content`           | Links must have text             |
| `anchor-is-valid`              | Links must have valid href       |
| `aria-props`                   | ARIA attributes must be valid    |
| `aria-proptypes`               | ARIA values must be valid        |
| `aria-role`                    | ARIA roles must be valid         |
| `aria-unsupported-elements`    | No ARIA on unsupported elements  |
| `heading-has-content`          | Headings must have text          |
| `html-has-lang`                | `<html>` must have lang          |
| `iframe-has-title`             | iframes must have title          |
| `img-redundant-alt`            | No "image" in alt text           |
| `role-has-required-aria-props` | Required ARIA attrs present      |
| `role-supports-aria-props`     | ARIA attrs match role            |
| `scope`                        | scope only on `<th>`             |
| `tabindex-no-positive`         | No positive tabindex             |
| `no-distracting-elements`      | No `<marquee>`, `<blink>`        |
| `no-access-key`                | No accessKey (conflicts with SR) |
| `no-redundant-roles`           | No role="button" on `<button>`   |

**Important Rules (WARN - encourage, don't block):**

| Rule                                     | Purpose                        |
| ---------------------------------------- | ------------------------------ |
| `click-events-have-key-events`           | Keyboard support for clicks    |
| `interactive-supports-focus`             | Interactive elements focusable |
| `label-has-associated-control`           | Labels linked to inputs        |
| `no-noninteractive-element-interactions` | No handlers on non-interactive |
| `no-static-element-interactions`         | Divs with handlers need role   |
| `no-noninteractive-tabindex`             | No tabindex on non-interactive |
| `mouse-events-have-key-events`           | Keyboard for mouse events      |
| `no-autofocus`                           | Avoid autofocus                |
| `media-has-caption`                      | Video/audio need captions      |
| `autocomplete-valid`                     | Valid autocomplete values      |

```javascript
// eslint.config.mjs - Full configuration
// See apps/web/eslint.config.mjs for complete implementation
```
