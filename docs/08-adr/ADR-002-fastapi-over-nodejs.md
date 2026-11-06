# ADR-002: FastAPI Over Node.js for Backend

## Status

**Accepted** - 2026-01-25

## Context

We need to choose a backend framework for our trading signals API. The backend must:

- Handle ML model inference
- Provide REST API for frontend
- Support WebSockets for real-time updates
- Integrate with Python ML libraries (XGBoost, pandas, numpy)

## Decision Drivers

1. **ML Integration**: XGBoost and pandas are Python libraries
2. **Performance**: Need < 50ms signal generation latency
3. **Developer experience**: Type safety and auto-documentation
4. **Ecosystem**: Exchange APIs, technical analysis libraries
5. **Team expertise**: Existing Python ML code in trading_bots project

## Considered Options

### Option A: FastAPI (Python) - Chosen

**Pros**:

- Native integration with ML libraries (XGBoost, pandas, numpy)
- Async support out of the box
- Automatic OpenAPI/Swagger documentation
- Pydantic for request/response validation
- High performance (21K+ req/s with uvicorn)
- Strong typing with Python type hints

**Cons**:

- Need two languages in monorepo (Python + TypeScript)
- Python deployment slightly more complex than Node.js

### Option B: Node.js (Express/Fastify) - Rejected

**Pros**:

- Same language as frontend (TypeScript everywhere)
- Large ecosystem
- Easy deployment (Vercel serverless)

**Cons**:

- **Critical**: Would need to call Python ML code via subprocess/microservice
- Adds 50-100ms latency for ML inference
- No native pandas/XGBoost support
- Would need separate Python service anyway

### Option C: Hybrid (Node.js API + Python ML Service) - Rejected

**Pros**:

- Best of both worlds theoretically
- Separation of concerns

**Cons**:

- **Two services to maintain and deploy**
- Inter-service communication latency
- Complexity explosion for MVP
- More infrastructure cost

## Decision

**Choose Option A: FastAPI** for the following reasons:

1. **Direct ML Integration**: XGBoost models run in the same process
2. **No IPC Overhead**: Signal generation stays < 50ms
3. **Existing Code**: trading_bots project has Python ML code to adapt
4. **Simpler Architecture**: One backend service, not two

## Architecture Impact

```
┌─────────────────┐     ┌─────────────────┐
│   Next.js       │────►│   FastAPI       │
│   Frontend      │     │   Backend       │
│   (TypeScript)  │     │   (Python)      │
└─────────────────┘     │                 │
                        │  ┌───────────┐  │
                        │  │ XGBoost   │  │
                        │  │ In-Process│  │
                        │  └───────────┘  │
                        └─────────────────┘
```

## Performance Comparison

| Framework                   | Requests/sec | ML Integration | Latency  |
| --------------------------- | ------------ | -------------- | -------- |
| FastAPI                     | 21,000+      | Native         | 5ms      |
| Express + Python subprocess | 8,000        | IPC call       | 50-100ms |
| Express + gRPC to Python    | 10,000       | Network call   | 20-50ms  |

## Consequences

### Positive

- ML inference < 5ms in-process
- Single deployment artifact for API
- Leverage existing Python ML code
- Auto-generated API documentation

### Negative

- Two languages in codebase
- Team must know both Python and TypeScript
- Need Python-specific hosting (Railway, not Vercel)

### Mitigations

- Clear separation: Python for backend, TypeScript for frontend
- Shared types package for API contracts
- Use Railway for easy Python deployment

## Future Reconsideration Triggers

This decision should be revisited ONLY if:

| Trigger               | Threshold                                       | Action                   |
| --------------------- | ----------------------------------------------- | ------------------------ |
| WebSocket connections | > 5,000 concurrent                              | Consider Node.js gateway |
| REST throughput       | FastAPI hitting limits after horizontal scaling | Evaluate alternatives    |
| Team composition      | Major shift to Node.js expertise                | Re-evaluate              |

**Note**: Adding more FastAPI replicas should be tried FIRST before adding Node.js.

See also: [INFRASTRUCTURE.md - Scaling Considerations](../06-devops/INFRASTRUCTURE.md#scaling-considerations-future)

---

## References

- [FastAPI Performance](https://fastapi.tiangolo.com/)
- Reference: trading_bots/backend/core
- [Python vs Node.js for ML APIs](https://realpython.com/api-integration-in-python/)
