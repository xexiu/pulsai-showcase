# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://github.com/xexiu/pulsai-showcase/security/advisories/new),
not in a public issue. You will get an acknowledgement within 72 hours.

## What runs on every push

- **TruffleHog** secret scan over the full git history (`.github/workflows/ci.yml`).
- **CodeQL** static analysis, `security-and-quality` queries (`.github/workflows/codeql.yml`).
- **OpenSSF Scorecard** supply-chain checks (`.github/workflows/scorecard.yml`).
- **Dependabot** weekly updates for Python dependencies and GitHub Actions; every action is pinned to a commit SHA.
