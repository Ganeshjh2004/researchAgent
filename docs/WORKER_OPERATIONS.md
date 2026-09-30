# Worker Operations

## Queue Architecture
The system utilizes a bespoke, lightweight Redis queue mechanism. 
1. **API Node:** Pushes a generated `task_id` into the Redis List `research:queue`.
2. **Worker Node:** Blocks on `research:queue` using `BLMOVE`. Tasks are atomically moved to `research:processing` and assumed ownership by the worker.

## Worker Startup
To start a worker process locally:
```powershell
.\venv\Scripts\python.exe worker.py
```
You can run multiple worker instances across different terminal tabs to achieve concurrent processing. Each worker assigns itself a unique `WORKER_ID` derived from its OS process ID.

## Task Lifecycle
1. **Queued:** `api.py` initialized the `task:{task_id}` hash and `LPUSH`ed the id.
2. **Running:** `worker.py` popped the ID, set status to `running`, and recorded a `started_at` timestamp.
3. **Completed / Failed:** Execution finished, and the state was updated with output or error metadata.

## Recovery Behavior (Stale Tasks)
Because this is a bespoke queue, exact consistency under hard-crash scenarios requires specific handling. If a worker process is unexpectedly terminated (e.g., `kill -9` or server crash), the task it was handling is orphaned in the `running` state inside `research:processing`.

**Detection & Remediation:**
Upon startup and before every polling cycle, `worker.py` runs a `recover_abandoned_tasks()` sweep. It scans the `research:processing` list for tasks.
While running, active workers pulse a `last_heartbeat` timestamp to the task hash every 10 seconds. If a task in the processing queue has not received a heartbeat in more than 35 seconds (the visibility timeout), it is deemed abandoned.
Abandoned tasks are safely and atomically moved back to `research:queue` for retry. A retry counter is maintained; if a task exceeds `MAX_RETRIES` (2), it is safely permanently failed.

## Troubleshooting
- **Timeout reading from socket:** If your Redis network fluctuates, the worker safely handles `redis.exceptions.TimeoutError` or drops the connection gracefully, sleeping for 5 seconds before retrying the connection to Redis.
- **Task Stuck in Running:** Restart a worker process to trigger the stale-task sweep.
