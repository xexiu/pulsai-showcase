# PulsAI Naming Conventions

## Overview

Consistent naming across the codebase improves readability, maintainability, and collaboration.

> **RULE**: When in doubt, be EXPLICIT over clever.

---

## General Principles

1. **Descriptive**: Names should describe what, not how
2. **Pronounceable**: You should be able to say the name out loud
3. **Searchable**: Avoid single letters (except loop indices)
4. **No abbreviations**: Write `configuration` not `cfg` (except industry standards)
5. **Consistent**: Same concept = same name across codebase

---

## File Naming

### TypeScript/JavaScript Files

```
Pattern: kebab-case.ts or kebab-case.tsx

✅ Good:
- user-service.ts
- create-trade.use-case.ts
- dashboard-layout.tsx
- use-auth.ts
- trade.schema.ts

❌ Bad:
- UserService.ts (PascalCase for files)
- createTrade.ts (camelCase)
- dashboard_layout.tsx (snake_case)
```

### Python Files

```
Pattern: snake_case.py

✅ Good:
- user_service.py
- create_trade_use_case.py
- xgboost_model.py
- test_user_repository.py

❌ Bad:
- UserService.py (PascalCase)
- create-trade.py (kebab-case)
```

### Test Files

```
TypeScript: *.test.ts, *.spec.ts
Python: test_*.py, *_test.py

✅ Good:
- user-service.test.ts
- test_user_repository.py
- create-trade.spec.ts

❌ Bad:
- userServiceTest.ts
- UserRepositoryTests.py
```

### Component Files (React)

```
Pattern: PascalCase.tsx for components

✅ Good:
- TradeCard.tsx
- SignalList.tsx
- DashboardLayout.tsx

❌ Bad:
- trade-card.tsx (use PascalCase for React components)
- tradeCard.tsx (camelCase)
```

---

## Variable & Function Naming

### TypeScript/JavaScript

```typescript
// Variables: camelCase
const userId = '123';
const isAuthenticated = true;
const tradeHistory = [];

// Constants: SCREAMING_SNAKE_CASE
const MAX_RETRY_ATTEMPTS = 3;
const API_BASE_URL = 'https://api.pulsai.com';
const DEFAULT_TIMEOUT_MS = 5000;

// Functions: camelCase, verb prefix
function getUserById(id: string): User {}
function calculateProfit(trade: Trade): number {}
function isValidEmail(email: string): boolean {}

// Boolean variables: is/has/can/should prefix
const isLoading = true;
const hasPermission = false;
const canTrade = true;
const shouldRefresh = false;

// Event handlers: handle prefix
function handleClick() {}
function handleSubmit() {}
function handleTradeExecuted() {}

// Async functions: verb describing action
async function fetchUserTrades(): Promise<Trade[]> {}
async function createOrder(): Promise<Order> {}
async function syncPortfolio(): Promise<void> {}
```

### Python

```python
# Variables: snake_case
user_id = "123"
is_authenticated = True
trade_history = []

# Constants: SCREAMING_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3
API_BASE_URL = "https://api.pulsai.com"
DEFAULT_TIMEOUT_MS = 5000

# Functions: snake_case, verb prefix
def get_user_by_id(user_id: str) -> User:
    pass

def calculate_profit(trade: Trade) -> Decimal:
    pass

def is_valid_email(email: str) -> bool:
    pass

# Boolean variables: is/has/can/should prefix
is_loading = True
has_permission = False
can_trade = True

# Private functions: single underscore prefix
def _validate_input(data: dict) -> None:
    pass

# "Private" (name mangling): double underscore (rarely used)
def __internal_method(self) -> None:
    pass
```

---

## Class Naming

### TypeScript

```typescript
// Classes: PascalCase, noun
class UserService {}
class TradeRepository {}
class SignalGenerator {}

// Interfaces: PascalCase, no I prefix
interface User {}
interface TradeConfig {}
interface SignalResult {}

// Types: PascalCase
type UserId = string;
type TradeAction = 'BUY' | 'SELL' | 'HOLD';
type SignalConfidence = number;

// Enums: PascalCase, singular
enum TradeStatus {
  PENDING = 'pending',
  EXECUTED = 'executed',
  CANCELLED = 'cancelled',
}

// Generic type parameters: single uppercase letter or descriptive
function identity<T>(arg: T): T {
  return arg;
}
function mapEntity<TEntity, TDto>(entity: TEntity): TDto {}
```

### Python

```python
# Classes: PascalCase, noun
class UserService:
    pass

class TradeRepository:
    pass

class SignalGenerator:
    pass

# Dataclasses/Entities: PascalCase
@dataclass
class User:
    id: UUID
    email: str

@dataclass
class Trade:
    id: UUID
    symbol: str

# Enums: PascalCase class, UPPER values
class TradeStatus(Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"

# Type aliases: PascalCase
UserId = str
TradeAction = Literal["BUY", "SELL", "HOLD"]
```

---

## Database Naming

### Tables

```sql
-- Pattern: snake_case, plural

✅ Good:
- users
- trades
- exchange_connections
- api_keys
- ohlcv_data

❌ Bad:
- User (singular, PascalCase)
- trade (singular)
- exchangeConnections (camelCase)
```

### Columns

```sql
-- Pattern: snake_case

✅ Good:
- id
- user_id
- created_at
- updated_at
- is_active
- exchange_name

❌ Bad:
- userId (camelCase)
- CreatedAt (PascalCase)
- isactive (no underscore)
```

### Foreign Keys

```sql
-- Pattern: {referenced_table_singular}_id

✅ Good:
- user_id (references users.id)
- trade_id (references trades.id)
- exchange_connection_id

❌ Bad:
- userId
- fk_user
- user_fk_id
```

### Indexes

```sql
-- Pattern: idx_{table}_{column(s)}

✅ Good:
- idx_users_email
- idx_trades_user_id_created_at
- idx_ohlcv_symbol_time

❌ Bad:
- users_email_index
- trade_idx
```

### Constraints

```sql
-- Pattern: {table}_{column}_{type}

✅ Good:
- users_email_unique
- trades_user_id_fkey
- users_email_check

❌ Bad:
- unique_email
- fk_1
```

---

## API Naming

### REST Endpoints

```
Pattern: /api/v1/{resource}/{id?}/{sub-resource}

✅ Good:
GET    /api/v1/users
GET    /api/v1/users/123
POST   /api/v1/users
PUT    /api/v1/users/123
DELETE /api/v1/users/123
GET    /api/v1/users/123/trades
POST   /api/v1/signals/generate

❌ Bad:
GET    /api/v1/getUsers (verb in URL)
GET    /api/v1/user (singular)
POST   /api/v1/createUser (verb in URL)
GET    /api/v1/Users (PascalCase)
```

### Query Parameters

```
Pattern: snake_case

✅ Good:
?page=1&page_size=20
?start_date=2024-01-01
?is_active=true
?sort_by=created_at&sort_order=desc

❌ Bad:
?pageSize=20 (camelCase)
?startDate=2024-01-01 (camelCase)
```

### Request/Response Bodies

```json
// Pattern: camelCase for JSON

✅ Good:
{
  "userId": "123",
  "firstName": "John",
  "createdAt": "2024-01-01T00:00:00Z",
  "isActive": true
}

❌ Bad:
{
  "user_id": "123",
  "FirstName": "John"
}
```

---

## Domain-Driven Design Naming

### Entities

```python
# Pattern: Business noun, no suffix

✅ Good:
class User:
    pass

class Trade:
    pass

class Signal:
    pass

❌ Bad:
class UserEntity:  # Redundant suffix
    pass
```

### Value Objects

```python
# Pattern: Descriptive noun

✅ Good:
class Email:
    value: str

class Symbol:
    base: str
    quote: str

class Money:
    amount: Decimal
    currency: str

❌ Bad:
class EmailVO:  # Redundant suffix
    pass
```

### Repositories

```python
# Pattern: {Entity}Repository

✅ Good:
class UserRepository:
    pass

class TradeRepository:
    pass

❌ Bad:
class UserRepo:  # Abbreviation
    pass

class UsersRepository:  # Plural
    pass
```

### Use Cases

```python
# Pattern: {Verb}{Noun}UseCase

✅ Good:
class CreateTradeUseCase:
    pass

class GetUserByIdUseCase:
    pass

class GenerateSignalUseCase:
    pass

❌ Bad:
class TradeCreator:  # Not explicit
    pass

class CreateTrade:  # Missing UseCase suffix
    pass
```

### Services

```python
# Pattern: {Domain}Service

✅ Good:
class TradingService:
    pass

class NotificationService:
    pass

❌ Bad:
class TradingHelper:  # "Helper" is vague
    pass

class TradingSvc:  # Abbreviation
    pass
```

---

## React Component Naming

### Components

```typescript
// Pattern: PascalCase, descriptive noun

✅ Good:
function TradeCard(): ReactNode { }
function SignalList(): ReactNode { }
function DashboardHeader(): ReactNode { }
function PortfolioSummary(): ReactNode { }

❌ Bad:
function tradeCard(): ReactNode { }  // camelCase
function Trade_Card(): ReactNode { } // snake_case
function TC(): ReactNode { }         // Abbreviation
```

### Hooks

```typescript
// Pattern: use{Noun/Verb}

✅ Good:
function useAuth(): AuthContext { }
function useTrades(): TradeState { }
function useWebSocket(): WebSocketConnection { }
function useLocalStorage<T>(key: string): T { }

❌ Bad:
function authHook(): AuthContext { }     // Missing use prefix
function UseAuth(): AuthContext { }      // PascalCase
function use_auth(): AuthContext { }     // snake_case
```

### Props

```typescript
// Pattern: {ComponentName}Props

✅ Good:
interface TradeCardProps {
  trade: Trade;
  onSelect: (trade: Trade) => void;
}

interface SignalListProps {
  signals: Signal[];
  isLoading: boolean;
}

❌ Bad:
interface Props { }           // Not descriptive
interface TradeCardParams { } // Wrong suffix
```

---

## Environment Variables

```bash
# Pattern: SCREAMING_SNAKE_CASE with prefix

✅ Good:
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_SECRET=...
NEXT_PUBLIC_API_URL=...  # Next.js public
VITE_API_URL=...         # Vite public

❌ Bad:
databaseUrl=...          # camelCase
database-url=...         # kebab-case
db_url=...               # Abbreviation
```

---

## Git Branch Naming

```bash
# Pattern: {type}/{ticket-id}-{description}

✅ Good:
feature/PULS-123-add-trading-signals
bugfix/PULS-456-fix-login-error
hotfix/PULS-789-security-patch
chore/PULS-101-update-dependencies
refactor/PULS-202-simplify-auth

❌ Bad:
add-trading-signals      # Missing type
feature/addTradingSignals # camelCase
Feature/PULS-123         # PascalCase type
```

---

## Summary Table

| Context              | Convention         | Example             |
| -------------------- | ------------------ | ------------------- |
| **TS Files**         | kebab-case         | `user-service.ts`   |
| **PY Files**         | snake_case         | `user_service.py`   |
| **React Components** | PascalCase         | `TradeCard.tsx`     |
| **TS Variables**     | camelCase          | `userId`            |
| **PY Variables**     | snake_case         | `user_id`           |
| **Constants**        | SCREAMING_SNAKE    | `MAX_RETRIES`       |
| **Classes**          | PascalCase         | `UserService`       |
| **Interfaces**       | PascalCase         | `User`              |
| **DB Tables**        | snake_case, plural | `users`             |
| **DB Columns**       | snake_case         | `created_at`        |
| **API Endpoints**    | /kebab-case/       | `/api/v1/users`     |
| **JSON Keys**        | camelCase          | `{"userId": "123"}` |
| **Env Vars**         | SCREAMING_SNAKE    | `DATABASE_URL`      |
| **Git Branches**     | type/description   | `feature/add-auth`  |
