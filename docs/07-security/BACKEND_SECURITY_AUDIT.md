# Backend Security Audit (apps/api)

**Purpose:** Backend-specific security checklist and findings. Use for periodic security passes and release gates.  
**Policy SoT:** [SECURITY_GUIDELINES.md](./SECURITY_GUIDELINES.md) — mandatory practices; this doc records **audit results** and BE-specific checks.  
**Scope:** `apps/api` (FastAPI, Celery, persistence, exchange, ML surface).  
**Companion:** [BACKEND_ARCHITECT_AUDIT.md](../04-structural/BACKEND_ARCHITECT_AUDIT.md) for architecture and entry points; BACKEND_FILE_INVENTORY.md for module roles.

---

## 1. Why This Doc Is Separate

- **SoT:** Security _policy_ lives in `SECURITY_GUIDELINES.md`. Security _audit_ (what we checked, what we found) lives here — one place for BE security findings.
- **Update trigger:** This doc is updated when you run a security pass or fix a finding; guidelines change when policy changes.
- **Scope:** BE-only. Frontend or full-stack audits can be separate docs under `07-security/`.

See [BACKEND_ARCHITECT_AUDIT.md §18](../04-structural/BACKEND_ARCHITECT_AUDIT.md#18-scope-and-related-audits-per-file-inventory-security-pass) for rationale (inventory + security in separate docs).

---

## 2. Last Audit

| Field               | Value                                                |
| ------------------- | ---------------------------------------------------- |
| **Last audit date** | _YYYY-MM-DD_                                         |
| **Auditor / role**  | _e.g. Main architect, security lead_                 |
| **Scope**           | _e.g. Full BE; or: auth + API + workers only_        |
| **Summary**         | _e.g. No critical issues; 2 medium in rate limiting_ |

---

## 3. Backend Security Checklist

Use this list during a pass. Tick when verified; note exceptions or findings in §4.

### 3.1 Authentication & session

- [ ] JWT: secret from env/settings only, never in code or repo.
- [ ] JWT: algorithm fixed (e.g. HS256); no `alg: none` or key confusion.
- [ ] Access token short-lived; refresh token revocable (e.g. blacklist).
- [ ] Password hashing: strong scheme (e.g. Argon2); no plaintext or weak hashes.
- [ ] Session middleware (OAuth): secret and cookie settings (same_site, https_only in prod).
- [ ] No auth bypass on admin routes (e.g. `AdminUser` / RBAC enforced).

### 3.2 Input validation & injection

- [ ] All API inputs validated (Pydantic/schemas); no trust of client data.
- [ ] SQL/ORM: parameterized only; no raw SQL with string formatting.
- [ ] Exchange/CCXT: symbol and timeframe validated against allowlist (e.g. VALID_TIMEFRAMES, symbol format).
- [ ] File/path: no user-controlled paths to model storage or scripts (admin-only or internal).

### 3.3 Secrets & config

- [ ] No secrets in code or default config; use env/settings.
- [ ] Logs: no passwords, tokens, or API keys (mask or omit).
- [ ] Redis/DB URLs: from config; not hardcoded.

### 3.4 Rate limiting & DoS

- [ ] Auth endpoints: rate limited (e.g. login, register, password reset).
- [ ] API: global or per-route limits where required (see SECURITY_GUIDELINES).
- [ ] Celery: task rate limits and time limits to avoid resource exhaustion.
- [ ] WebSocket: connection limits and message size if applicable.

### 3.5 Error handling & information leakage

- [ ] Global exception handler returns generic message to client (no stack traces, DB details).
- [ ] PulsAIException and status codes used consistently (see `infrastructure/exceptions.py`).
- [ ] Logs: full details server-side only; no sensitive data in JSON response.

### 3.6 Dependencies

- [ ] Dependencies scanned (e.g. `pip audit`, or Snyk/Dependabot); known vulns addressed.
- [ ] Pin versions in requirements; avoid `*` or loose ranges for production.

### 3.7 Data & storage

- [ ] DB: principle of least privilege (service accounts with minimal required access).
- [ ] Sensitive data at rest: encryption as per SECURITY_GUIDELINES (e.g. API keys).
- [ ] Model storage (local/R2): access control and no public read of credentials.

### 3.8 Celery & workers

- [ ] Broker (Redis): auth and TLS in production; not exposed publicly.
- [ ] Task args: no raw secrets in task payloads; use refs or env.
- [ ] Worker: fork-safety (e.g. OMP_NUM_THREADS=1) to avoid crashes; no unintended privilege escalation.

### 3.9 CORS & headers

- [ ] CORS: allowlist origins; no `*` in production for credentialed requests.
- [ ] Security headers (e.g. CSP, X-Frame-Options) where applicable (see SECURITY_GUIDELINES).

---

## 4. Findings Log

Record issues here; move to “Resolved” when fixed and re-audited.

| ID                | Date         | Severity            | Description                              | Location / recommendation               | Status          |
| ----------------- | ------------ | ------------------- | ---------------------------------------- | --------------------------------------- | --------------- |
| _e.g. BE-SEC-001_ | _YYYY-MM-DD_ | High / Medium / Low | _e.g. Rate limit missing on /auth/login_ | _e.g. application/auth/rate_limiter.py_ | Open / Resolved |

---

## 5. Cross-Links

- **Policy and practices:** [SECURITY_GUIDELINES.md](./SECURITY_GUIDELINES.md)
- **BE architecture and entry points:** [BACKEND_ARCHITECT_AUDIT.md](../04-structural/BACKEND_ARCHITECT_AUDIT.md)
- **BE module catalog:** BACKEND_FILE_INVENTORY.md
- **Lay audit (release gate):** [BACKEND_ARCHITECT_AUDIT.md §17](../04-structural/BACKEND_ARCHITECT_AUDIT.md#17-lay-audit-checklist-missing-pieces--release-gate)
