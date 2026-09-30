# Architectural Decisions

## 1. Task Persistence via Redis Hashes
**Context:** We needed a way to track asynchronous API tasks explicitly, decoupling the HTTP response from the 10-20 second LLM agent execution loop.
**Decision:** We utilized Redis `hset` / `hgetall` storing simple JSON-serializable strings (`task:{task_id}`).
**Why:** Redis was already provisioned for LangGraph check-pointing. Reusing it for simple API state meant we didn't have to introduce PostgreSQL or SQLite. Redis Hashes give O(1) lookups for task statuses.
**Drawback:** In-memory databases are volatile. We use a 7-day TTL to auto-expire task states, preventing memory bloat.

## 2. Asynchronous Execution via FastAPI BackgroundTasks
**Context:** The API must not block while LangGraph executes.
**Decision:** We used `fastapi.BackgroundTasks`.
**Why:** It is the simplest zero-dependency implementation of fire-and-forget logic in FastAPI. It fulfills the immediate goal without over-engineering (e.g., Celery, RabbitMQ).
**Drawback:** If the Uvicorn process restarts or crashes, any currently running `BackgroundTasks` are immediately lost. There is no automatic retry queue.

## 3. Dedicated `reports/` Directory
**Context:** The previous setup saved `.txt` files directly in the root directory alongside source code.
**Decision:** Created a forced `reports/` subdirectory and updated `tools.py` to write explicitly to that path.
**Why:** Operational cleanliness and security. Isolating generated artifacts prevents accidental `.gitignore` pollution and makes path-traversal prevention highly effective (the API only needs to look inside one folder).

## 4. LLM API Rate-Limit Tolerance
**Context:** DuckDuckGo and Wikipedia frequently time out or return 403s on repeated rapid testing.
**Decision:** The research workflow catches these exceptions, logs them, and returns an empty or degraded state. The API accepts this and sets `status = "failed"`.
**Why:** We must never fabricate data. A missing search result is accurately propagated to the client as a graceful failure, rather than crashing the Python process.
