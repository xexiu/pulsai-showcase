# PulsAI DDD Patterns

## Overview

This document clarifies WHERE and HOW to apply Domain-Driven Design (DDD) in PulsAI.

> **CRITICAL**: DDD is NOT for all code. Apply it where business complexity exists.

---

## Where to Apply DDD

### ✅ YES - Apply DDD Here

| Layer           | Components                               | Why DDD                                 |
| --------------- | ---------------------------------------- | --------------------------------------- |
| **Domain**      | Entities, Value Objects, Domain Services | Core business logic, complex rules      |
| **Application** | Use Cases, DTOs, Application Services    | Orchestrates domain, enforces workflows |

### ❌ NO - Skip DDD Here

| Layer               | Components                               | Why NOT DDD                                  |
| ------------------- | ---------------------------------------- | -------------------------------------------- |
| **Infrastructure**  | Database repos, API clients, ML wrappers | Technical implementations, no business logic |
| **Presentation**    | UI components, API routes                | Display logic only                           |
| **Utilities**       | Date formatters, string helpers, config  | Simple, no business rules                    |
| **CRUD Operations** | Simple read/write without business rules | Overkill for simple operations               |

---

## Architecture Layers

```
src/
├── domain/              # ✅ DDD - Core business logic
│   ├── entities/        # Trade, Position, Signal, User
│   ├── value-objects/   # Price, Quantity, Symbol, TimeFrame
│   ├── repositories/    # INTERFACES ONLY (no implementations)
│   ├── services/        # RiskManager, PositionSizer
│   └── events/          # TradeExecuted, SignalGenerated
│
├── application/         # ✅ DDD - Use cases & orchestration
│   ├── use-cases/       # ExecuteTrade, GenerateSignal, CreateUser
│   ├── dtos/            # Input/Output objects
│   └── services/        # Application-level orchestration
│
├── infrastructure/      # ❌ NO DDD - Technical implementations
│   ├── database/        # SQLAlchemy repositories (implement domain interfaces)
│   ├── exchange/        # CCXT wrapper, API clients
│   ├── ml/              # XGBoost wrapper, model loading
│   └── messaging/       # Redis pub/sub, notifications
│
└── lib/                 # ❌ NO DDD - Utilities
    ├── utils/           # Date helpers, string formatters
    ├── config/          # Settings, environment
    └── constants/       # Application constants
```

---

## Trading execution and modes (PulsAI — composition, not `BaseTrading` inheritance)

Do **not** model `DemoTrading → PaperTrading → LiveTrading` as an OOP inheritance chain. That would break **Liskov** (live is not a superset of demo semantics), invite **god base classes**, and duplicate venue rules across overrides.

**Actual design (SRP + SOLID):**

| Concern                                   | Mechanism                                                                                                                            |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| HTTP / product entry                      | `UnifiedTradingService`                                                                                                              |
| Mode-specific orchestration               | **Strategy**: `DemoModeHandler`, `PaperModeHandler`, `LiveTradingModeHandler` (small surfaces; no shared “base trading” class)       |
| CCXT execution + persistence              | `PaperTradingService` for **both** paper and live; `ccxt_use_mainnet` + gates distinguish sandbox vs mainnet                         |
| Demo-only aggregate                       | `DemoTradingService` + `demo_*` tables (separate bounded context)                                                                    |
| Read models (Estadísticas, equity, daily) | Application services over repos; **paper** and **live** share queries with a **ledger partition** on `paper_orders.ccxt_use_mainnet` |

**SoT:** `docs/04-structural/TRADING_DOMAIN_BOUNDARIES.md` and `src/domain/services/trading_live_execution_mode.py` (`ccxt_use_mainnet_for_exchange_stats_mode` for API `mode` → boolean).

---

## Domain Layer (DDD)

### Entities

Entities have identity and lifecycle. They contain business rules.

```python
# domain/entities/trade.py
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Optional

from domain.value_objects import Symbol, Side, Price, Quantity
from domain.events import TradeExecutedEvent


@dataclass
class Trade:
    """
    Trade entity - represents a single trade execution.

    Business Rules:
    - Trade must have valid symbol (exists on exchange)
    - Quantity must be positive
    - Price must be positive
    - Stop loss must be below entry for BUY, above for SELL
    """

    id: UUID = field(default_factory=uuid4)
    symbol: Symbol = field(default=None)
    side: Side = field(default=None)
    quantity: Quantity = field(default=None)
    entry_price: Price = field(default=None)
    stop_loss: Optional[Price] = field(default=None)
    take_profit: Optional[Price] = field(default=None)
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = field(default=None)
    status: str = field(default="pending")

    # Domain events
    _events: list = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate business rules on creation."""
        self._validate_stop_loss()

    def _validate_stop_loss(self) -> None:
        """
        Business Rule: Stop loss must make sense for the trade direction.
        - BUY trade: stop loss must be BELOW entry price
        - SELL trade: stop loss must be ABOVE entry price
        """
        if self.stop_loss is None:
            return

        if self.side == Side.BUY:
            if self.stop_loss.value >= self.entry_price.value:
                raise ValueError(
                    f"Stop loss ({self.stop_loss}) must be below entry price "
                    f"({self.entry_price}) for BUY trades"
                )

        if self.side == Side.SELL:
            if self.stop_loss.value <= self.entry_price.value:
                raise ValueError(
                    f"Stop loss ({self.stop_loss}) must be above entry price "
                    f"({self.entry_price}) for SELL trades"
                )

    def execute(self, execution_price: Price) -> None:
        """
        Execute the trade at given price.

        Business Rule: Can only execute pending trades.
        """
        if self.status != "pending":
            raise ValueError(f"Cannot execute trade in '{self.status}' status")

        self.status = "executed"
        self.executed_at = datetime.utcnow()

        # Emit domain event
        self._events.append(
            TradeExecutedEvent(
                trade_id=self.id,
                symbol=self.symbol,
                side=self.side,
                quantity=self.quantity,
                price=execution_price,
                timestamp=self.executed_at,
            )
        )

    def cancel(self, reason: str) -> None:
        """Cancel the trade with a reason."""
        if self.status != "pending":
            raise ValueError(f"Cannot cancel trade in '{self.status}' status")

        self.status = "cancelled"

    def collect_events(self) -> list:
        """Collect and clear domain events."""
        events = self._events.copy()
        self._events.clear()
        return events
```

### Value Objects

Value Objects are immutable and defined by their attributes, not identity.

```python
# domain/value_objects/price.py
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)  # Immutable
class Price:
    """
    Price value object - represents a monetary value.

    Business Rules:
    - Must be positive
    - Maximum 8 decimal places (crypto standard)
    """

    value: Decimal

    def __post_init__(self) -> None:
        # Validate on creation
        if self.value <= 0:
            raise ValueError(f"Price must be positive, got {self.value}")

        # Round to 8 decimal places
        rounded = self.value.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        object.__setattr__(self, "value", rounded)

    def __str__(self) -> str:
        return f"${self.value:,.8f}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Price):
            return False
        return self.value == other.value

    def __lt__(self, other: "Price") -> bool:
        return self.value < other.value

    def __le__(self, other: "Price") -> bool:
        return self.value <= other.value

    def add(self, other: "Price") -> "Price":
        """Add two prices (returns new Price)."""
        return Price(self.value + other.value)

    def multiply(self, factor: Decimal) -> "Price":
        """Multiply price by factor (returns new Price)."""
        return Price(self.value * factor)


@dataclass(frozen=True)
class Symbol:
    """
    Trading pair symbol value object.

    Business Rules:
    - Must be in format BASE/QUOTE (e.g., BTC/USDT)
    - Base and quote must be 3-5 characters
    """

    base: str
    quote: str

    def __post_init__(self) -> None:
        if not (3 <= len(self.base) <= 5):
            raise ValueError(f"Base currency must be 3-5 chars: {self.base}")
        if not (3 <= len(self.quote) <= 5):
            raise ValueError(f"Quote currency must be 3-5 chars: {self.quote}")

        # Normalize to uppercase
        object.__setattr__(self, "base", self.base.upper())
        object.__setattr__(self, "quote", self.quote.upper())

    def __str__(self) -> str:
        return f"{self.base}/{self.quote}"

    @classmethod
    def from_string(cls, symbol: str) -> "Symbol":
        """Create Symbol from string like 'BTC/USDT'."""
        if "/" not in symbol:
            raise ValueError(f"Invalid symbol format: {symbol}")

        parts = symbol.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid symbol format: {symbol}")

        return cls(base=parts[0], quote=parts[1])


@dataclass(frozen=True)
class Quantity:
    """
    Trade quantity value object.

    Business Rules:
    - Must be positive
    - Must respect minimum order size (exchange-specific)
    """

    value: Decimal

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(f"Quantity must be positive, got {self.value}")
```

### Domain Services

Domain services contain business logic that doesn't belong to a single entity.

```python
# domain/services/risk_manager.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from domain.entities import Trade, Position
from domain.value_objects import Price, Quantity


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_size_pct: Decimal = Decimal("0.02")  # 2% of portfolio
    max_daily_loss_pct: Decimal = Decimal("0.05")     # 5% daily loss limit
    max_leverage: Decimal = Decimal("1.0")            # 1x = no leverage (spot)
    risk_reward_ratio: Decimal = Decimal("2.0")       # Minimum 1:2 RR


class RiskManager:
    """
    Domain Service: Manages trading risk.

    Business Rules:
    - Never risk more than X% of portfolio per trade
    - Stop daily trading if daily loss exceeds Y%
    - Enforce minimum risk/reward ratio
    """

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def calculate_position_size(
        self,
        portfolio_value: Decimal,
        entry_price: Price,
        stop_loss_price: Price,
    ) -> Quantity:
        """
        Calculate safe position size based on risk parameters.

        Formula: Position Size = (Portfolio * Risk%) / (Entry - StopLoss)
        """
        risk_amount = portfolio_value * self.config.max_position_size_pct
        price_risk = abs(entry_price.value - stop_loss_price.value)

        if price_risk == 0:
            raise ValueError("Entry price and stop loss cannot be the same")

        size = risk_amount / price_risk
        return Quantity(value=size)

    def validate_trade(
        self,
        trade: Trade,
        current_daily_pnl: Decimal,
        portfolio_value: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate trade against risk rules.

        Returns: (is_valid, error_message)
        """
        # Check daily loss limit
        daily_loss_pct = -current_daily_pnl / portfolio_value
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            return False, f"Daily loss limit reached: {daily_loss_pct:.2%}"

        # Check risk/reward ratio
        if trade.take_profit and trade.stop_loss:
            potential_profit = abs(trade.take_profit.value - trade.entry_price.value)
            potential_loss = abs(trade.entry_price.value - trade.stop_loss.value)

            if potential_loss == 0:
                return False, "Stop loss too close to entry"

            risk_reward = potential_profit / potential_loss
            if risk_reward < self.config.risk_reward_ratio:
                return False, f"Risk/reward {risk_reward:.2f} below minimum {self.config.risk_reward_ratio}"

        return True, None
```

---

## Application Layer (DDD)

### Use Cases

Use cases orchestrate domain objects to fulfill business requirements.

```python
# application/use_cases/execute_trade.py
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from domain.entities import Trade
from domain.services import RiskManager
from domain.repositories import TradeRepository, PositionRepository
from domain.value_objects import Symbol, Side, Price, Quantity


@dataclass
class ExecuteTradeInput:
    """Input DTO for execute trade use case."""
    user_id: UUID
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class ExecuteTradeOutput:
    """Output DTO for execute trade use case."""
    trade_id: UUID
    status: str
    executed_price: Optional[float] = None
    error: Optional[str] = None


class ExecuteTradeUseCase:
    """
    Use Case: Execute a trade for a user.

    Steps:
    1. Validate input
    2. Check risk limits
    3. Create trade entity
    4. Execute via exchange
    5. Persist and emit events
    """

    def __init__(
        self,
        trade_repository: TradeRepository,
        position_repository: PositionRepository,
        risk_manager: RiskManager,
        exchange_client,  # Infrastructure - injected
    ) -> None:
        self._trade_repo = trade_repository
        self._position_repo = position_repository
        self._risk_manager = risk_manager
        self._exchange = exchange_client

    async def execute(self, input_dto: ExecuteTradeInput) -> ExecuteTradeOutput:
        """Execute the use case."""

        # 1. Create domain objects
        symbol = Symbol.from_string(input_dto.symbol)
        side = Side(input_dto.side)
        quantity = Quantity(value=input_dto.quantity)
        entry_price = Price(value=input_dto.entry_price)

        stop_loss = None
        if input_dto.stop_loss:
            stop_loss = Price(value=input_dto.stop_loss)

        take_profit = None
        if input_dto.take_profit:
            take_profit = Price(value=input_dto.take_profit)

        # 2. Create trade entity (validates business rules)
        trade = Trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        # 3. Validate risk
        portfolio_value = await self._position_repo.get_portfolio_value(input_dto.user_id)
        daily_pnl = await self._position_repo.get_daily_pnl(input_dto.user_id)

        is_valid, error = self._risk_manager.validate_trade(
            trade=trade,
            current_daily_pnl=daily_pnl,
            portfolio_value=portfolio_value,
        )

        if not is_valid:
            return ExecuteTradeOutput(
                trade_id=trade.id,
                status="rejected",
                error=error,
            )

        # 4. Execute on exchange
        try:
            execution_result = await self._exchange.create_order(
                symbol=str(symbol),
                side=str(side),
                quantity=float(quantity.value),
            )

            # 5. Update trade with execution
            trade.execute(Price(value=execution_result.price))

            # 6. Persist
            await self._trade_repo.save(trade)

            return ExecuteTradeOutput(
                trade_id=trade.id,
                status="executed",
                executed_price=float(execution_result.price),
            )

        except Exception as e:
            return ExecuteTradeOutput(
                trade_id=trade.id,
                status="failed",
                error=str(e),
            )
```

---

## Infrastructure Layer (NO DDD)

Infrastructure implements domain interfaces with technical details.

```python
# infrastructure/database/trade_repository_impl.py
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from domain.entities import Trade
from domain.repositories import TradeRepository
from infrastructure.database.models import TradeModel


class SQLAlchemyTradeRepository(TradeRepository):
    """
    SQLAlchemy implementation of TradeRepository.

    NOTE: This is infrastructure code - no DDD patterns here.
    Just technical implementation of the domain interface.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, trade: Trade) -> None:
        """Persist trade to database."""
        model = TradeModel(
            id=trade.id,
            symbol=str(trade.symbol),
            side=str(trade.side),
            quantity=float(trade.quantity.value),
            entry_price=float(trade.entry_price.value),
            stop_loss=float(trade.stop_loss.value) if trade.stop_loss else None,
            take_profit=float(trade.take_profit.value) if trade.take_profit else None,
            status=trade.status,
            created_at=trade.created_at,
            executed_at=trade.executed_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def find_by_id(self, trade_id: UUID) -> Optional[Trade]:
        """Find trade by ID."""
        result = await self._session.execute(
            select(TradeModel).where(TradeModel.id == trade_id)
        )
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    def _to_entity(self, model: TradeModel) -> Trade:
        """Convert database model to domain entity."""
        # Simple mapping - no business logic
        return Trade(
            id=model.id,
            symbol=Symbol.from_string(model.symbol),
            side=Side(model.side),
            quantity=Quantity(value=model.quantity),
            entry_price=Price(value=model.entry_price),
            stop_loss=Price(value=model.stop_loss) if model.stop_loss else None,
            take_profit=Price(value=model.take_profit) if model.take_profit else None,
            status=model.status,
            created_at=model.created_at,
            executed_at=model.executed_at,
        )
```

---

## Utilities Layer (NO DDD)

Simple helpers with no business logic.

```python
# lib/utils/date_helpers.py
from datetime import datetime, timezone


def now_utc() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def format_timestamp(dt: datetime) -> str:
    """Format datetime for API responses."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_timestamp(s: str) -> datetime:
    """Parse ISO format timestamp."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
```

```python
# lib/config/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings - NO DDD, just config."""

    database_url: str
    redis_url: str
    api_key: str

    class Config:
        env_file = ".env"


settings = Settings()
```

---

## Summary: DDD Decision Matrix

| Ask Yourself                            | YES → DDD   | NO → Simple Code   |
| --------------------------------------- | ----------- | ------------------ |
| Does it contain business rules?         | ✅ Use DDD  | ❌ Skip DDD        |
| Can it affect trading decisions?        | ✅ Use DDD  | ❌ Skip DDD        |
| Does it have complex state transitions? | ✅ Use DDD  | ❌ Skip DDD        |
| Is it just data transformation?         | ❌ Skip DDD | ✅ Simple function |
| Is it just database CRUD?               | ❌ Skip DDD | ✅ Repository      |
| Is it a utility function?               | ❌ Skip DDD | ✅ Simple helper   |

**Remember**: DDD adds complexity. Only use it where complexity already exists in the business domain.
