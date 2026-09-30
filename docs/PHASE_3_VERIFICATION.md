# Phase 3 Verification Report

## Verified Facts

1. **Does the FastAPI application import and start successfully?**
   Yes. `api.py` initializes a FastAPI instance cleanly and can be run via `uvicorn api:app`.

2. **What exactly does `run_research_workflow()` return?**
   It returns a `dict` representing the final `WorkflowState` after the LangGraph execution completes or fails.

3. **Does it invoke the real LangGraph graph?**
   Yes, it invokes `app.invoke(initial_state, config=config)` which executes the `StateGraph`.

4. **How are Redis checkpoints configured?**
   `RedisSaver.from_conn_string(REDIS_URI)` is used as the `checkpointer` argument to `graph.compile()`.

5. **Does Redis store task results, or only graph checkpoints?**
   It only stores LangGraph checkpoints. There is currently no dedicated task storage table/key for the API layer to store task status independently of LangGraph.

6. **Are task IDs and thread IDs distinct or shared?**
   Currently, there are no separate "task IDs". The API generates a UUID and uses it directly as the LangGraph `thread_id`.

7. **Does the API block while the LLM runs?**
   Yes, the `POST /api/v1/research` endpoint is fully synchronous and blocks the HTTP request handler until the graph completes.

8. **Can concurrent requests interfere with each other?**
   LangGraph state is isolated by `thread_id`. However, CPU-bound parsing and blocking I/O (like `save_to_txt`) tie up Uvicorn's default thread pool.

9. **What happens if the process crashes during execution?**
   The HTTP request fails and the client gets no response. The LangGraph state is left partially saved in Redis, but no background worker exists to automatically resume or report the failure asynchronously.

10. **How are output filenames generated?**
    In `research_workflow.py`, `validate_input` generates `research_{slug}_{stamp}.txt`. The `_safe_filename` helper strips unsafe characters to prevent path traversal.

11. **Where are research `.txt` reports currently saved?**
    They are saved in the project root directory (`D:\AI Agent`), because `save_to_txt` uses relative paths (`with open(filename, "a")`).

12. **Are error messages sanitized?**
    Yes. Unhandled exceptions are caught by `api.py` and converted to a generic 500 error (`"Internal workflow error occurred."`), preventing stack traces/keys from leaking. Expected agent errors are returned in the `error` field.

13. **Are request limits enforced?**
    Yes. The `ResearchRequest` Pydantic model enforces `min_length=3` and `max_length=500` on the `query`.

14. **Which tests actually exist and can run?**
    - `test_research_workflow.py` (8 workflow tests)
    - `test_api.py` (7 API unit/contract tests)
    - `e2e_test_api.py` (1 live end-to-end integration test)

## Defects & Unverified Assumptions

- **Defect:** API requests are fully synchronous. A 15+ second research task blocks the connection, risking client timeouts and thread-pool exhaustion.
- **Defect:** `.txt` files are polluting the root directory.
- **Assumption:** We assume Redis is always available. The graph crashes hard if Redis is down, because `RedisSaver.from_conn_string` attempts to connect synchronously.

## Next Steps for Phase 4
- Implement async task execution with a proper status lifecycle.
- Update `tools.py` (or workflow) to place `.txt` files in `reports/`.
- Restructure documentation into `docs/`.
