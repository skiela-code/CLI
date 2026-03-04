# ADR-001: Background Job Approach

## Status
Accepted

## Context
Document generation involves multiple async operations: loading data, calling Claude AI API, rendering DOCX, and running red-flag checks. This can take 2–15 seconds. We need a way to run these tasks without blocking the HTTP response.

Options considered:
1. **Celery + Redis** — Industry standard for Python background jobs
2. **ARQ (async Redis queue)** — Lightweight async alternative to Celery
3. **asyncio.create_task()** — In-process async task execution
4. **FastAPI BackgroundTasks** — Built-in but limited

## Decision
We chose **asyncio.create_task()** for V1.

## Rationale

| Criterion | Celery+Redis | ARQ | asyncio.create_task | FastAPI BG |
|-----------|-------------|-----|-------------------|------------|
| Extra infra | Redis + workers | Redis | None | None |
| Async native | No (sync) | Yes | Yes | Partial |
| Job durability | Yes | Yes | No | No |
| Complexity | High | Medium | Low | Low |
| Retry control | Yes | Yes | Via tenacity | No |
| Status tracking | Via backend | Via backend | Via DB | No |

For V1:
- **Simplicity wins**: No Redis container, no worker processes, no serialization.
- **I/O-bound work**: Document generation is API calls + file I/O — ideal for asyncio.
- **Status via DB**: We track status through `Document.status` and `DocumentVersion` existence. The UI polls with HTMX.
- **Retries**: External API calls use `tenacity` for retry logic.
- **Acceptable trade-off**: Tasks don't survive server restarts. Generation takes seconds and can be re-triggered.

## Consequences
- Generation tasks are lost on server restart (acceptable for V1)
- Memory-bounded by event loop capacity (acceptable for small-medium workloads)
- Migration path to ARQ is straightforward since generation function is already async

## Migration Path (V2)
If needed, add ARQ: define the same async function as an ARQ task, add Redis to docker-compose, configure a worker. ~30 minutes of work.
