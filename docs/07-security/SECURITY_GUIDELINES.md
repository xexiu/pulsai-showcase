# PulsAI Security Guidelines

## Overview

Security is **NON-NEGOTIABLE** for a trading platform. A single vulnerability could result in:

- **Financial loss** for users
- **Legal liability** for the company
- **Reputation destruction**

This document defines mandatory security practices.

For the **trading and automation HTTP surface** (authorization matrix, **Idempotency-Key** matrix, rate-limit alignment, structured error-code inventory, and a compact threat model), see [TRADING_AUTOMATION_API_SECURITY_CONTRACT.md](./TRADING_AUTOMATION_API_SECURITY_CONTRACT.md).

---

## 1. Security Principles

### 1.1 Defense in Depth

Multiple layers of security. If one fails, others protect.

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1: Network                         │
│  - Cloudflare DDoS protection                               │
│  - Rate limiting at edge                                    │
│  - WAF (Web Application Firewall)                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 2: Application                     │
│  - Input validation                                         │
│  - Authentication (JWT)                                     │
│  - Authorization (RBAC)                                     │
│  - CORS restrictions                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 3: Data                            │
│  - Encryption at rest                                       │
│  - Encryption in transit (TLS 1.3)                          │
│  - API key encryption                                       │
│  - Database access controls                                 │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Principle of Least Privilege

Every component gets ONLY the permissions it needs.

```yaml
# BAD - Service has full database access
DATABASE_URL=postgresql://admin:password@db/pulsai

# GOOD - Service has minimal permissions
# API service (read/write users, trades)
API_DATABASE_URL=postgresql://api_user:xxx@db/pulsai

# Worker service (read/write models, signals)
WORKER_DATABASE_URL=postgresql://worker_user:xxx@db/pulsai

# Read-only analytics
ANALYTICS_DATABASE_URL=postgresql://readonly_user:xxx@db/pulsai
```

### 1.3 Fail Secure

When errors occur, fail to a secure state.

```python
# BAD - Fails open (allows access on error)
def check_authorization(user: User, resource: str) -> bool:
    try:
        return authorization_service.check(user, resource)
    except Exception:
        return True  # DANGEROUS: Allows access on error

# GOOD - Fails closed (denies access on error)
def check_authorization(user: User, resource: str) -> bool:
    try:
        return authorization_service.check(user, resource)
    except Exception as e:
        logger.error(f"Authorization check failed: {e}")
        return False  # SAFE: Denies access on error
```

---

## 2. Authentication Security

### 2.1 Password Requirements

```python
from passlib.context import CryptContext
import re

pwd_context = CryptContext(
    schemes=["argon2"],  # Use Argon2, NOT bcrypt
    deprecated="auto",
)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password meets security requirements.

    Requirements:
    - 8-128 characters
    - At least 1 uppercase
    - At least 1 lowercase
    - At least 1 digit
    - At least 1 special character
    - Not in common password list
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"

    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must be at most {MAX_PASSWORD_LENGTH} characters"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"

    if is_common_password(password):
        return False, "Password is too common"

    return True, "Password is valid"

def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

### 2.2 JWT Token Security

```python
from datetime import datetime, timedelta
from typing import Optional
import jwt

# Configuration
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]  # 256-bit random key
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(
    user_id: str,
    additional_claims: Optional[dict] = None,
) -> str:
    """Create short-lived access token."""
    now = datetime.utcnow()

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    """Create longer-lived refresh token."""
    now = datetime.utcnow()

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
        "jti": str(uuid.uuid4()),  # Unique token ID for revocation
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_token(token: str, expected_type: str = "access") -> Optional[dict]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        if payload.get("type") != expected_type:
            return None

        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

### 2.3 Rate Limiting (Login)

```python
from fastapi import HTTPException, Request
from redis import Redis
import time

redis_client = Redis.from_url(os.environ["REDIS_URL"])

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes

async def check_login_rate_limit(request: Request, email: str) -> None:
    """
    Rate limit login attempts.

    - Max 5 attempts per 15 minutes per IP
    - Max 5 attempts per 15 minutes per email
    """
    ip_address = request.client.host

    # Check IP rate limit
    ip_key = f"login_attempts:ip:{ip_address}"
    ip_attempts = redis_client.get(ip_key)

    if ip_attempts and int(ip_attempts) >= MAX_LOGIN_ATTEMPTS:
        ttl = redis_client.ttl(ip_key)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Try again in {ttl} seconds.",
        )

    # Check email rate limit
    email_key = f"login_attempts:email:{email}"
    email_attempts = redis_client.get(email_key)

    if email_attempts and int(email_attempts) >= MAX_LOGIN_ATTEMPTS:
        ttl = redis_client.ttl(email_key)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts for this account. Try again in {ttl} seconds.",
        )

async def record_failed_login(request: Request, email: str) -> None:
    """Record a failed login attempt."""
    ip_address = request.client.host

    # Increment IP counter
    ip_key = f"login_attempts:ip:{ip_address}"
    pipe = redis_client.pipeline()
    pipe.incr(ip_key)
    pipe.expire(ip_key, LOCKOUT_DURATION_SECONDS)
    pipe.execute()

    # Increment email counter
    email_key = f"login_attempts:email:{email}"
    pipe = redis_client.pipeline()
    pipe.incr(email_key)
    pipe.expire(email_key, LOCKOUT_DURATION_SECONDS)
    pipe.execute()

async def clear_login_attempts(request: Request, email: str) -> None:
    """Clear login attempts after successful login."""
    ip_address = request.client.host
    redis_client.delete(f"login_attempts:ip:{ip_address}")
    redis_client.delete(f"login_attempts:email:{email}")
```

---

## 3. API Key Security (Exchange Keys)

### 3.1 Encryption at Rest

```python
from cryptography.fernet import Fernet
import base64
import os

# Generate encryption key (store in secure vault, not env vars for production)
# ENCRYPTION_KEY = Fernet.generate_key()

class APIKeyEncryption:
    """Encrypt/decrypt user API keys."""

    def __init__(self, encryption_key: bytes):
        self.fernet = Fernet(encryption_key)

    def encrypt(self, api_key: str) -> str:
        """Encrypt API key for storage."""
        encrypted = self.fernet.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_key: str) -> str:
        """Decrypt API key for use."""
        decoded = base64.urlsafe_b64decode(encrypted_key.encode())
        return self.fernet.decrypt(decoded).decode()

# Usage
encryption = APIKeyEncryption(os.environ["API_KEY_ENCRYPTION_KEY"].encode())

# When user adds API key
encrypted_api_key = encryption.encrypt(user_provided_api_key)
# Store encrypted_api_key in database

# When we need to use the key
api_key = encryption.decrypt(stored_encrypted_key)
# Use api_key to make exchange API calls
```

### 3.2 Key Permissions Validation

```python
import ccxt

async def validate_exchange_api_key(
    exchange_name: str,
    api_key: str,
    api_secret: str,
) -> dict:
    """
    Validate that API key has correct permissions.

    Required: Read (balance, orders)
    Required: Trade (place orders)
    FORBIDDEN: Withdraw (should be disabled)
    """
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({
        'apiKey': api_key,
        'secret': api_secret,
    })

    result = {
        "valid": False,
        "can_read": False,
        "can_trade": False,
        "can_withdraw": False,  # Should be False
        "error": None,
    }

    try:
        # Test read permission
        await exchange.fetch_balance()
        result["can_read"] = True

        # Test trade permission (small limit order, immediately cancel)
        # This is exchange-specific, some allow checking without placing order
        result["can_trade"] = True  # Assume true if read works

        # Check if withdrawal is enabled (we don't want this!)
        # This varies by exchange - some expose this info
        permissions = exchange.describe().get('has', {})
        if permissions.get('withdraw'):
            result["can_withdraw"] = True
            result["error"] = "SECURITY WARNING: API key has withdrawal permission. Please create a key without withdrawal permission."
            return result

        result["valid"] = True

    except ccxt.AuthenticationError as e:
        result["error"] = f"Invalid API credentials: {e}"
    except ccxt.PermissionDenied as e:
        result["error"] = f"Insufficient permissions: {e}"
    except Exception as e:
        result["error"] = f"Validation failed: {e}"

    return result
```

---

## 4. Input Validation

### 4.1 Validation Layer (Python)

```python
from pydantic import BaseModel, Field, validator, constr
from decimal import Decimal
from typing import Literal
import re

class CreateOrderRequest(BaseModel):
    """Validated order creation request."""

    symbol: constr(regex=r"^[A-Z]{2,10}/[A-Z]{2,10}$")  # e.g., "BTC/USDT"
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    amount: Decimal = Field(gt=0, le=Decimal("1000000"))
    price: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"))

    @validator("symbol")
    def validate_symbol(cls, v: str) -> str:
        """Validate trading pair format."""
        allowed_bases = {"BTC", "ETH", "SOL", "BNB"}
        allowed_quotes = {"USDT", "USD", "EUR"}

        base, quote = v.split("/")

        if base not in allowed_bases:
            raise ValueError(f"Base currency {base} not supported")

        if quote not in allowed_quotes:
            raise ValueError(f"Quote currency {quote} not supported")

        return v

    @validator("price")
    def validate_price(cls, v: Decimal | None, values: dict) -> Decimal | None:
        """Price required for limit orders."""
        if values.get("type") == "limit" and v is None:
            raise ValueError("Price required for limit orders")

        return v

# Usage in FastAPI
@router.post("/orders")
async def create_order(request: CreateOrderRequest, user: User = Depends(get_current_user)):
    # request is already validated by Pydantic
    pass
```

### 4.2 SQL Injection Prevention

```python
# BAD - SQL injection vulnerable
def get_user_by_email(email: str):
    query = f"SELECT * FROM users WHERE email = '{email}'"  # NEVER DO THIS
    return db.execute(query)

# GOOD - Parameterized query
def get_user_by_email(email: str) -> User | None:
    query = "SELECT * FROM users WHERE email = :email"
    result = db.execute(query, {"email": email})
    return result.fetchone()

# BETTER - Use ORM (SQLAlchemy)
def get_user_by_email(email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()
```

### 4.3 XSS Prevention (Frontend)

```typescript
// BAD - XSS vulnerable
function UserMessage({ message }: { message: string }) {
  return <div dangerouslySetInnerHTML={{ __html: message }} />;  // NEVER
}

// GOOD - React auto-escapes
function UserMessage({ message }: { message: string }) {
  return <div>{message}</div>;  // React escapes HTML automatically
}

// If HTML is needed, sanitize first
import DOMPurify from 'dompurify';

function SafeHTML({ html }: { html: string }) {
  const sanitized = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a'],
    ALLOWED_ATTR: ['href'],
  });

  return <div dangerouslySetInnerHTML={{ __html: sanitized }} />;
}
```

---

## 5. Secret Management

### 5.1 Environment Variables

```bash
# .env.example (committed to git)
DATABASE_URL=postgresql://user:password@localhost:5432/pulsai
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=your-secret-key-here
ANTHROPIC_API_KEY=sk-ant-xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx

# .env (NEVER committed to git)
# Copy .env.example and fill with real values
```

### 5.2 Secret Scanning

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Full history for scanning

      - name: Install TruffleHog
        run: |
          curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/v3.95.2/scripts/install.sh \
            | sh -s -- -b /usr/local/bin v3.95.2

      - name: Scan for secrets
        shell: bash
        run: |
          trufflehog git file://. \
            --since-commit "${{ github.event.repository.default_branch }}" \
            --branch HEAD \
            --fail \
            --no-update \
            --github-actions \
            --only-verified

  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Snyk to check for vulnerabilities
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high
```

### 5.3 Gitignore Security

```gitignore
# Secrets - NEVER commit these
.env
.env.local
.env.*.local
*.pem
*.key
secrets/
credentials.json
service-account.json

# IDE with potential secrets
.idea/
.vscode/settings.json

# Database dumps
*.sql
*.dump
backups/

# Logs with potential sensitive data
*.log
logs/
```

---

## 6. API Security

### 6.1 Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# General API rate limiting
@app.get("/api/portfolio")
@limiter.limit("100/minute")  # 100 requests per minute per IP
async def get_portfolio(request: Request):
    pass

# Stricter for sensitive operations
@app.post("/api/orders")
@limiter.limit("10/minute")  # 10 orders per minute
async def create_order(request: Request, order: CreateOrderRequest):
    pass

# Very strict for auth operations
@app.post("/auth/login")
@limiter.limit("5/15minute")  # 5 login attempts per 15 minutes
async def login(request: Request, credentials: LoginRequest):
    pass
```

### 6.2 CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

# Production CORS - restrictive
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pulsai.live",
        "https://www.pulsai.live",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Development CORS - more permissive
if os.environ.get("ENVIRONMENT") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### 6.3 Security Headers

```python
from fastapi import Response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Strict Transport Security
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://api.pulsai.live wss://api.pulsai.live;"
    )

    return response
```

### 6.4 Write-endpoint audit (auth and rate limit)

All state-changing endpoints (POST, PUT, PATCH, DELETE) are documented for **auth** and **rate limit** so abuse and DoS are controlled.

**Public (no auth) — rate limited**

| Endpoint                         | Method | Auth | Rate limit                     | Notes                                                                                                                                                      |
| -------------------------------- | ------ | ---- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/v1/signals/generate`       | POST   | None | Yes (per IP, configurable/min) | For dev/testing and chart/TG verification. In production may require auth or be restricted to internal use. Celery worker does not use this HTTP endpoint. |
| `/api/v1/newsletter_subscribers` | POST   | None | Yes (per IP, configurable/min) | Prevents list stuffing and DB bloat.                                                                                                                       |

**Auth (login/register)** — login and forgot-password are rate limited or lockout; register and reset-password may be rate limited per IP in future.

**User (CurrentUser required)** — backtests, comparisons, profile/settings; user-scoped. Optional per-user rate limits on create if abuse appears.

**AI** — `/api/v1/ai/explain-signal` and `/api/v1/ai/analyze-chart` are rate limited (in-memory per identity). Admin AI endpoints require AdminUser.

**Admin** — All admin routes require AdminUser or SuperAdminUser; no per-endpoint rate limit (acceptable for admin-only).

Config: `signals_generate_rate_limit_per_minute`, `newsletter_subscribe_rate_limit_per_minute` in settings. See `src.api.rate_limit` for implementation.

**SoT (NO-DRY):** Client IP extraction is in `src.utils.request_utils.get_client_ip` (used by auth, rate_limit, audit_service, error_handler). Per-minute in-memory rate limit logic is in `src.api.rate_limit.check_rate_limit` (used by signals, newsletter, and AI endpoints).

### 6.5 Stripe billing

User routes (`checkout-session`, `portal-session`, invoices) require JWT. **Checkout and portal** accept `Idempotency-Key` (replay via `ApiHttpIdempotencyService`). Rate limits are per user+IP; see [BILLING_API_SECURITY.md](../02-technical/BILLING_API_SECURITY.md) and [API_RATE_LIMIT_ROUTE_MATRIX.md](../02-technical/API_RATE_LIMIT_ROUTE_MATRIX.md).

`POST /api/v1/billing/webhook` does **not** use JWT auth. Trust is established with Stripe’s `Stripe-Signature` header and `STRIPE_WEBHOOK_SECRET` (`billing_webhook.py` → `verify_stripe_payload`). Events are applied **idempotently** (dedupe by Stripe event id). Do not log signing secrets or full card data from payloads.

---

## 7. Database Security

### 7.1 Connection Security

```python
# PostgreSQL connection with SSL
DATABASE_URL = (
    f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    "?sslmode=require"
    "&sslrootcert=/path/to/ca-certificate.crt"
)

# Connection pooling with limits
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,  # Base connections
    max_overflow=10,  # Additional connections under load
    pool_timeout=30,  # Wait time for connection
    pool_recycle=1800,  # Recycle connections every 30 minutes
)
```

### 7.2 Role-Based Access Control

```sql
-- Create roles with specific permissions
CREATE ROLE pulsai_api_user LOGIN PASSWORD 'secure_password';
CREATE ROLE pulsai_worker_user LOGIN PASSWORD 'secure_password';
CREATE ROLE pulsai_readonly LOGIN PASSWORD 'secure_password';

-- API user: Can read/write users, trades, orders
GRANT SELECT, INSERT, UPDATE ON users TO pulsai_api_user;
GRANT SELECT, INSERT, UPDATE ON trades TO pulsai_api_user;
GRANT SELECT, INSERT, UPDATE ON orders TO pulsai_api_user;

-- Worker: Can read/write signals, models
GRANT SELECT, INSERT, UPDATE ON signals TO pulsai_worker_user;
GRANT SELECT, INSERT, UPDATE ON models TO pulsai_worker_user;
GRANT SELECT ON users TO pulsai_worker_user;  -- Read-only for users

-- Read-only: For analytics, monitoring
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pulsai_readonly;
```

---

## 8. Logging & Audit

### 8.1 Security Audit Logging

```python
import structlog
from datetime import datetime
from typing import Optional

logger = structlog.get_logger()

class SecurityAuditLog:
    """Log security-relevant events."""

    @staticmethod
    def login_attempt(
        email: str,
        ip_address: str,
        success: bool,
        failure_reason: Optional[str] = None,
    ) -> None:
        logger.info(
            "login_attempt",
            event_type="authentication",
            email=email,
            ip_address=ip_address,
            success=success,
            failure_reason=failure_reason,
            timestamp=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def api_key_created(user_id: str, exchange: str) -> None:
        logger.info(
            "api_key_created",
            event_type="api_key",
            user_id=user_id,
            exchange=exchange,
            timestamp=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def trade_executed(
        user_id: str,
        symbol: str,
        side: str,
        amount: str,
        price: str,
    ) -> None:
        logger.info(
            "trade_executed",
            event_type="trade",
            user_id=user_id,
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            timestamp=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def suspicious_activity(
        user_id: str,
        activity_type: str,
        details: dict,
    ) -> None:
        logger.warning(
            "suspicious_activity",
            event_type="security_alert",
            user_id=user_id,
            activity_type=activity_type,
            details=details,
            timestamp=datetime.utcnow().isoformat(),
        )
```

### 8.2 Never Log Sensitive Data

```python
# BAD - Logging sensitive data
logger.info(f"User logged in with password: {password}")  # NEVER
logger.info(f"API key: {api_key}")  # NEVER
logger.debug(f"Request body: {request.body}")  # Could contain secrets

# GOOD - Mask sensitive data
def mask_secret(secret: str) -> str:
    """Mask secret for logging, show only first/last 4 chars."""
    if len(secret) < 12:
        return "****"
    return f"{secret[:4]}...{secret[-4:]}"

logger.info(f"User {user.email} logged in")
logger.info(f"Using API key: {mask_secret(api_key)}")
```

---

## 9. Incident Response

### 9.1 Security Incident Procedure

```markdown
## If You Discover a Security Issue

1. **STOP** - Don't ignore it
2. **ISOLATE** - If active attack, disable affected component
3. **DOCUMENT** - Screenshot, logs, timestamps
4. **NOTIFY** - Contact security lead immediately
5. **INVESTIGATE** - Determine scope and impact
6. **REMEDIATE** - Fix the vulnerability
7. **REVIEW** - Post-incident analysis

## Contact

Security Lead: security@pulsai.live
Emergency: [phone number]
```

### 9.2 Compromised Credentials

```python
async def handle_compromised_api_keys(user_id: str) -> None:
    """Emergency procedure for compromised exchange API keys."""

    # 1. Immediately disable all trading
    await disable_user_trading(user_id)

    # 2. Revoke all API keys in our system
    await revoke_all_user_api_keys(user_id)

    # 3. Alert user
    await send_emergency_notification(
        user_id,
        subject="URGENT: API Keys Compromised",
        body="Your API keys may have been compromised. All trading has been disabled. Please rotate your exchange API keys immediately.",
    )

    # 4. Log incident
    SecurityAuditLog.suspicious_activity(
        user_id=user_id,
        activity_type="api_key_compromised",
        details={"action": "emergency_lockdown"},
    )

    # 5. Alert security team
    await alert_security_team(f"User {user_id} API keys potentially compromised")
```

---

## 10. Compliance (EU/Spain)

### 10.1 GDPR Requirements

```python
# User data export (GDPR Right to Data Portability)
async def export_user_data(user_id: str) -> dict:
    """Export all user data for GDPR compliance."""
    user = await get_user(user_id)
    trades = await get_user_trades(user_id)
    signals = await get_user_signals(user_id)

    return {
        "user": {
            "email": user.email,
            "created_at": user.created_at.isoformat(),
            "subscription_tier": user.subscription_tier,
        },
        "trades": [t.to_dict() for t in trades],
        "signals": [s.to_dict() for s in signals],
        "exported_at": datetime.utcnow().isoformat(),
    }

# User data deletion (GDPR Right to Erasure)
async def delete_user_data(user_id: str) -> None:
    """Delete all user data for GDPR compliance."""
    # 1. Delete related data first (foreign key constraints)
    await delete_user_trades(user_id)
    await delete_user_signals(user_id)
    await delete_user_api_keys(user_id)

    # 2. Delete user account
    await delete_user(user_id)

    # 3. Log for audit (keep audit log for legal compliance)
    logger.info(
        "user_data_deleted",
        user_id=user_id,
        timestamp=datetime.utcnow().isoformat(),
    )
```

### 10.2 Marketing email unsubscribe (newsletter)

- **Signed tokens:** Logged-out unsubscribe links use `itsdangerous.URLSafeTimedSerializer` with the app `secret_key` and a fixed salt (`src/infrastructure/security/newsletter_unsubscribe_token.py`). Tokens bind to `newsletter_subscribers.id` and expire after a bounded age.
- **Idempotent API:** `POST /api/v1/newsletter_subscribers/unsubscribe` returns `204` even when the token is invalid or expired, to avoid leaking whether an email exists in the system.
- **Stored state:** Marketing opt-out is recorded as `newsletter_subscribers.unsubscribed_at` (SoT for “do not send marketing” for that row).

---

## Future: HttpOnly Cookie Authentication (Sprint 3.2c)

> **STATUS**: Planned for future sprint. See ROADMAP.md Sprint 3.2c for implementation details.

### Why HttpOnly Cookies?

**Current approach** (localStorage tokens):

- Vulnerable to XSS attacks (JavaScript can read tokens)
- Requires manual token management in frontend
- Token visible in DevTools Application tab

**HttpOnly cookies approach**:

- Tokens inaccessible to JavaScript (XSS protection)
- Browser handles token storage automatically
- Server controls token lifecycle

### Benefits

| Aspect            | localStorage              | HttpOnly Cookie                |
| ----------------- | ------------------------- | ------------------------------ |
| XSS Protection    | ❌ JS can read            | ✅ JS cannot access            |
| Auto-inclusion    | ❌ Manual headers         | ✅ Browser sends automatically |
| Token visibility  | ❌ DevTools readable      | ✅ Hidden from client          |
| Logout complexity | ✅ Simple (clear storage) | ❌ Server roundtrip required   |
| CSRF risk         | ✅ Not auto-sent          | ❌ Requires CSRF protection    |

### Trade-offs

1. **Requires CSRF protection**: Cookies are auto-sent, enabling CSRF attacks
2. **Cannot check token expiry client-side**: Must rely on 401 responses
3. **More complex debugging**: Cannot inspect tokens in DevTools
4. **Server dependency for logout**: Client cannot clear httpOnly cookies

### Implementation Notes

**Cookie settings** (when implemented):

```python
# Backend cookie configuration
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,      # JS cannot access
    secure=True,        # HTTPS only
    samesite="strict",  # CSRF protection layer 1
    path="/",
    max_age=15 * 60,    # 15 minutes
)
```

**CSRF protection** (required with cookies):

```python
# Generate CSRF token (NOT in cookie, returned in response)
csrf_token = secrets.token_urlsafe(32)
response.headers["X-CSRF-Token"] = csrf_token

# Frontend stores in memory/localStorage and sends with requests
# Backend validates X-CSRF-Token header on state-changing requests
```

**Frontend changes** (when implemented):

```typescript
// All API calls must include credentials
fetch(url, {
  credentials: 'include', // Include cookies
  headers: {
    'X-CSRF-Token': getCSRFToken(),
  },
});
```

### Migration Path

1. Implement backend cookie support alongside current JWT in headers
2. Add CSRF token generation and validation
3. Update frontend to use credentials and CSRF headers
4. Remove localStorage token storage
5. Update logout to call server endpoint

---

## Security Checklist

Before any release:

```markdown
## Authentication

- [ ] Passwords hashed with Argon2
- [ ] JWT tokens short-lived (15 min)
- [ ] Refresh token rotation implemented
- [ ] Rate limiting on login

## Data Protection

- [ ] API keys encrypted at rest
- [ ] Database connections use SSL
- [ ] No secrets in code or logs

## Input Validation

- [ ] All inputs validated (Pydantic)
- [ ] SQL injection prevented (ORM/parameterized)
- [ ] XSS prevented (output encoding)

## API Security

- [ ] CORS configured correctly
- [ ] Rate limiting on all endpoints
- [ ] Security headers set

## Monitoring

- [ ] Audit logging enabled
- [ ] Suspicious activity alerts
- [ ] Failed login monitoring

## Compliance

- [ ] GDPR data export available
- [ ] Data deletion implemented
- [ ] Privacy policy updated
```
