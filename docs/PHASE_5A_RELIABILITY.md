# Phase 5A: Redis Worker Reliability Verification and Hardening

## 1. Actual Defects Found in Initial Phase 5 Implementation
1. **Task Loss on Crash:** `BRPOP` was used, which immediately removes tasks from the queue. If the worker crashed before updating the hash, the task was silently dropped from the queue but stuck in the hash forever.
2. **No Atomic Ownership:** Task claiming and execution logging were non-atomic.
3. **False Positives in Recovery:** The recovery sweep hardcoded a 600-second timeout. Any LangGraph execution genuinely taking longer than 10 minutes (due to rate limiting) would be violently marked failed.
4. **Lack of Idempotency:** The worker forcefully overwrote terminal states (`completed` or `failed`) with `HSET` without checking if the task was already aborted.
5. **No Safe Recovery:** Abandoned tasks were just marked `failed` rather than safely re-queued.

## 2. Queue Design and Delivery Semantics
We implemented an **at-least-once delivery** design with **idempotent state transitions**.
- **Atomic Claiming:** Tasks are moved from `research:queue` to `research:processing` atomically using `BLMOVE`.
- **Worker Heartbeats:** The worker runs a background thread that pulses a `last_heartbeat` timestamp to the task hash every 10 seconds.
- **Idempotency:** State transitions (from `running` to `completed`/`failed`) are strictly guarded by a Lua script that verifies the task is still in the `running` state before committing the result.

## 3. Recovery Behavior
- **Detection:** A sweep (`recover_abandoned_tasks`) executes periodically at the start of the worker loop. It scans the `research:processing` list.
- **Visibility Timeout:** A task is deemed abandoned if its `last_heartbeat` is older than `35` seconds.
- **Re-queuing & Retries:** Abandoned tasks are safely and atomically moved back to `research:queue`. A `retries` counter is incremented.
- **Terminal Protection:** If a task exceeds `MAX_RETRIES` (2), it is safely failed using the atomic Lua completion script, ensuring no overwrites occur if another worker miraculously wakes up.

## 4. Tests Executed
1. **Normal Task Execution:** Verified via `test_api.py` and `test_research_workflow.py`.
2. **Worker Crash & Recovery (`test_worker_recovery.py`):** 
   - A fake running task was injected directly into `research:processing` with a stale heartbeat.
   - The recovery sweep was manually invoked, which successfully detected it, moved it back to `research:queue`, and incremented the retries.
   - A second recovery simulation verified that exceeding max retries permanently failed the task.
3. **Real E2E Outcome (`e2e_test_api.py`):** Successfully executed `API -> Redis Queue -> Worker (BLMOVE) -> LangGraph -> Groq -> Report -> API Retrieval`.

## 5. Files Changed
- `worker.py`: Rewritten completely to include atomic queues, heartbeat threads, and Lua execution scripts.
- `api.py`: Updated the `task:{task_id}` schema to initialize `retries: 0`.
- `test_worker_recovery.py`: Created for hard-fault injection testing.
- `docs/PHASE_5A_RELIABILITY.md`: This report.
- `docs/WORKER_OPERATIONS.md`: Updated to reflect visibility timeouts and heartbeats.

## 6. Known Limitations
- The system is built around a single Redis instance. If the Redis server itself crashes and drops the AOF/RDB, queues are lost.
- LangGraph checkpoints currently grow indefinitely inside Redis.

## 7. Exact Startup Commands
To run the fully reliable distributed architecture:

**1. Redis:** Ensure Redis server is active on `localhost:6379`.
**2. API Server:**
```powershell
.\venv\Scripts\uvicorn.exe api:app --host 127.0.0.1 --port 8000
```
**3. Worker Daemon:**
```powershell
.\venv\Scripts\python.exe worker.py
```
You can spawn multiple `worker.py` instances to scale horizontally.
