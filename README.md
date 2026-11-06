# pulsai-showcase

[![CI](https://github.com/xexiu/pulsai-showcase/actions/workflows/ci.yml/badge.svg)](https://github.com/xexiu/pulsai-showcase/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xexiu/pulsai-showcase/actions/workflows/codeql.yml/badge.svg)](https://github.com/xexiu/pulsai-showcase/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/xexiu/pulsai-showcase/badge)](https://scorecard.dev/viewer/?uri=github.com/xexiu/pulsai-showcase)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=xexiu_pulsai-showcase&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=xexiu_pulsai-showcase)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=xexiu_pulsai-showcase&metric=coverage)](https://sonarcloud.io/summary/new_code?id=xexiu_pulsai-showcase)
[![Maintainability](https://sonarcloud.io/api/project_badges/measure?project=xexiu_pulsai-showcase&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=xexiu_pulsai-showcase)

A self-contained, runnable slice of the **PulsAI** backend — a FastAPI + Celery platform for market-data
analytics and ML research. The full product lives in a private monorepo; this repository is the part of it a
reviewer can clone, run and test in two minutes.

> Educational project. Nothing here is financial advice.

## What is in the slice

Four production modules, together with **everything they import** and every test that covers them:

| module | what it does | the engineering point |
|---|---|---|
| [`cache_aside.py`](backend/src/infrastructure/cache/cache_aside.py) | read-through Redis cache for JSON values, single and batch (`MGET`) | **fail-open on Redis faults only**: an outage degrades to the loader, but a `TypeError` in our own code still raises instead of becoming a permanent silent cache miss |
| [`redis_ttl_lock.py`](backend/src/infrastructure/cache/redis_ttl_lock.py) | `SET NX EX` lock with a per-holder token | each holder writes its own token and release is a `WATCH`/`MULTI` compare-and-delete, so a holder whose TTL lapsed can never delete the next holder's lock (a race reproduced, then fixed test-first) |
| [`http_concurrency.py`](backend/src/api/http_concurrency.py) | strong ETags and `If-Match` → `412 Precondition Failed` | optimistic concurrency for HTTP updates, no lost writes |
| [`ccxt_error_mapping.py`](backend/src/shared/ccxt_error_mapping.py) | exchange-library exceptions → stable error codes + safe messages | venue text never reaches users: no leaked IDs, i18n-able, a contract clients can rely on |

The slice is **89 source files and 31 test files (322 tests)**. It was produced by an export tool in the private
repo that copies the *import closure* of these modules, so nothing they need is missing and nothing they don't
need is carried.

## Run it

```bash
cd backend
uv sync
uv run pytest          # 322 tests, no Redis or database needed (fakeredis)
uv run ruff check .
uv run mypy
```

Python 3.14, dependencies pinned in [`backend/pyproject.toml`](backend/pyproject.toml).

## The full system (private repo), measured

| | |
|---|---|
| backend product code | 2,094 Python modules — `domain` / `application` / `infrastructure` / `api` layers (DDD) |
| backend tests | 2,266 test modules |
| frontend | Next.js + TypeScript, 3,247 source files, 1,568 test files |
| database | PostgreSQL, 110 Alembic migrations |
| decisions | 33 architecture decision records |
| CI | 14 jobs: lint, types, tests with a coverage gate on changed code, migrations, performance baselines, duplicate-code ratchet, secret scan, dependency audit |

## Quality signals on this repository

- **CI** — ruff (lint + format), mypy, pytest with coverage, on every push.
- **SonarQube Cloud** — quality gate, coverage and maintainability, from the CI run.
- **CodeQL** — static security analysis.
- **OpenSSF Scorecard** — supply-chain practices; every GitHub Action is pinned to a commit SHA.
- **TruffleHog** — secret scan of the full git history.

See [`SECURITY.md`](SECURITY.md) for how to report a vulnerability.

## License

[MIT](LICENSE)
