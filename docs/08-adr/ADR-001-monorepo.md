# ADR-001: Monorepo Architecture

## Status

**Accepted** - 2026-01-25

## Context

We need to decide how to organize our codebase:

- **Option A**: Monorepo (single repository for frontend, backend, shared code)
- **Option B**: Polyrepo (separate repositories for each service)

## Decision Drivers

1. **Team size**: Currently 1-2 developers
2. **Code sharing**: Need to share types between frontend and backend
3. **Deployment**: Different deployment targets (Vercel, Railway)
4. **CI/CD**: Want unified testing and linting
5. **Developer experience**: Simple local development setup

## Considered Options

### Option A: Monorepo (Chosen)

```
pulsai/
├── apps/
│   ├── web/          # Next.js frontend
│   └── api/          # FastAPI backend
├── packages/
│   └── shared/       # Shared types, constants
├── docs/             # Documentation
└── package.json      # Root workspace config
```

**Pros**:

- Single source of truth for all code
- Easy to share types and constants
- Atomic commits across frontend/backend
- Unified CI/CD pipeline
- Simpler local development (one clone)
- Path-based conditional deployment possible

**Cons**:

- Larger repository size over time
- Need monorepo tooling (Turborepo)
- All developers see all code (security consideration)

### Option B: Polyrepo (Rejected)

```
pulsai-web/       # Separate repo
pulsai-api/       # Separate repo
pulsai-shared/    # Separate repo (npm package)
```

**Pros**:

- Clear separation of concerns
- Independent deployment cycles
- Smaller repositories

**Cons**:

- Harder to share code (need to publish packages)
- Non-atomic changes across repos
- Multiple CI/CD pipelines to maintain
- Version synchronization challenges
- More complex local development

## Decision

**Choose Option A: Monorepo** using:

- **pnpm workspaces** for package management
- **Turborepo** for build orchestration
- **Path-based CI/CD** (only deploy changed apps)

## Consequences

### Positive

- Developers can make changes across stack in single PR
- Shared types ensure frontend/backend stay in sync
- Unified linting and testing standards
- Simpler onboarding (one repo to clone)

### Negative

- Need to learn Turborepo
- Must implement path-based deployment (done in CI_CD_PIPELINE.md)
- Repository will grow larger over time

### Mitigations

- Use `.gitignore` to exclude build artifacts
- Implement proper caching in CI
- Use Turborepo's remote caching for faster builds

## References

- [Turborepo Documentation](https://turbo.build/repo/docs)
- [pnpm Workspaces](https://pnpm.io/workspaces)
- [Monorepo vs Polyrepo](https://monorepo.tools/)
