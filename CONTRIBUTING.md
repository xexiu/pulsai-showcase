# Contributing

Feedback and pull requests are welcome.

## Get the code

```bash
git clone https://github.com/xexiu/pulsai-showcase
```

Build and test commands are in the README, section [Run it](README.md#run-it): `uv sync` and `uv run pytest` for the
backend, `pnpm install` and `pnpm --filter web test` for the frontend. Neither needs a database or Redis.

## Give feedback

- **Bug reports and enhancement requests:** open a [GitHub issue](https://github.com/xexiu/pulsai-showcase/issues).
  Say what you ran, what you expected and what happened.
- **Security problems:** do not open an issue. Follow [`SECURITY.md`](SECURITY.md) (private vulnerability reporting).
- **Questions and discussion:** use the issue tracker too. Issues are searchable and each has its own URL.

## Contribute a change

1. Fork the repository and branch from `main`.
2. Make the change. Keep it small and focused on one thing.
3. Open a pull request against `main`. The pull request is how every change is reviewed and merged.
4. All checks must pass before it merges:
   - **backend:** `ruff check`, `ruff format --check`, `mypy`, and `pytest` with coverage;
   - **frontend:** `tsc --noEmit` and `vitest` with coverage;
   - **CodeQL** (Python), **SonarQube Cloud** (its quality gate, which requires at least 80% coverage on new code) and
     the **TruffleHog** secret scan.

## Tests

A change that adds or changes behaviour comes with tests of that behaviour, in the same pull request. Bug fixes come
with a regression test that fails without the fix. Put tests beside the existing ones: `backend/tests`, `web/tests`,
and `web/property-tests` for property-based tests (fast-check). CI runs the full suites on every pull request, and a
pull request without tests for the new behaviour is asked to add them.

## Style

Follow what the linters enforce: ruff and mypy (strict) for Python, `tsc` strict for TypeScript. Write code and
comments in English.

## Where the code comes from

Most of `backend/src`, `backend/tests`, `web/src` and `web/tests` is produced by an export from a private repository
(see [How this slice was produced](README.md#how-this-slice-was-produced)); an export overwrites those paths. A
change to them is reviewed here, and the maintainer applies an accepted change to the private repository too, so the
next export keeps it. Files outside those paths (`.github`, `docs`, `web/property-tests`, this file) live only here.
