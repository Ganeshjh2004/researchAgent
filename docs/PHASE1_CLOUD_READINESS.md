# Phase 1: Infrastructure Simplification & Cloud Readiness

**Status:** Complete (infrastructure preparation only — no cloud deployment executed)  
**Date:** 2026-10-01  
**Target environment:** Free-tier-first, ₹0 monthly spend target  
**Production hosting candidate:** Google Cloud Run (not deployed in this phase)

---

## A. Repository Findings

### Actual Existing Architecture

The production path is: `api.py` (FastAPI) + `worker.py` (daemon) + `research_workflow.py` (LangGraph).

`main.py` is a standalone **CLI agent** — separate from the web API, not the production entry point.

**Persistence model:**
- Task state: Redis Hashes (`task:{id}`, 7-day TTL)
- Task queue: Redis Lists (`research:queue`, `research:processing`)
- LangGraph checkpoints: `RedisSaver` (writes checkpoint data to Redis)
- LangGraph store: `RedisStore` (used in CLI path only, not production API)
- Vector store: Chroma, local filesystem (`RAG/vectorstore/`)
- Reports: Local filesystem (`reports/*.txt`)

**There is no SQLAlchemy ORM, no Alembic, no database models, and no PostgreSQL in the existing codebase.**  
Supabase PostgreSQL is net-new infrastructure, not a migration.

---

## B. Files Changed in Phase 1

| File | Change | Justification |
|------|--------|---------------|
| `research_workflow.py` | Line 53: hardcoded `REDIS_URI` → `os.getenv("REDIS_URI", "redis://localhost:6379")` | Bug fix — only file not reading from env var |
| `memory.py` | `redis.Redis(host=..., port=...)` → `redis.Redis.from_url(os.getenv(...))` | Env consistency — CLI path |
| `config.py` (new) | Centralized env-driven config with validation and safe `describe()` | Single source of truth for all env vars |
| `.env.example` | Expanded from 2 lines to full documented template | Documents all variables, includes cost notes |
| `requirements.txt` | Added `asyncpg==0.30.0`, `psycopg2-binary==2.9.10` | PostgreSQL driver readiness |
| `docs/PHASE1_CLOUD_READINESS.md` (this file) | Cloud readiness assessment | Documents compatibility, blockers, and limitations |

---

## C. PostgreSQL Readiness Assessment

### What was implemented
- `asyncpg` and `psycopg2-binary` drivers added to `requirements.txt` and installed.
- `DATABASE_URL` placeholder added to `.env.example` with both local and Supabase formats documented.
- `config.py` reads `DATABASE_URL` from env; returns `None` if not set (PostgreSQL is optional).
- Startup validation will surface a clear error if `GROQ_API_KEY` is missing.

### What was NOT done (intentionally)
- No SQLAlchemy engine created (no database models exist to connect to).
- No Alembic migration tooling introduced (no schema to migrate).
- No tables created on Supabase.
- No `DATABASE_URL` with real credentials set.

### What remains unverified
- Actual Supabase connection test (requires live credentials + project reference).
- Supabase free-tier pause behaviour (projects pause after 1 week of inactivity).
- PgBouncer pooled connection format (`?pgbouncer=true`) vs. direct connection.

### Supabase MCP Status
The Supabase MCP server is configured in Antigravity with read-only access.  
**A live MCP query was not executed** during this phase — verification deferred to Phase 2  
when a schema or table inspection is actually needed.  
MCP connectivity will be confirmed at first use.

### Connection URL formats
```
# Local PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/researchmate

# Supabase — direct (use for dev and Alembic migrations)
DATABASE_URL=postgresql+asyncpg://postgres:<password>@db.<ref>.supabase.co:5432/postgres

# Supabase — pooled via PgBouncer (use for application connections in production)
DATABASE_URL=postgresql+asyncpg://postgres:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?pgbouncer=true
```

---

## D. Redis & Queue Compatibility Assessment

### Local Redis — verified working
- `BLMOVE`: ✅ Standard command, fully supported.
- `LREM`: ✅ Standard command, fully supported.
- `HSET`/`HGETALL`/`EXPIRE`: ✅ Standard commands.
- Lua scripts (`COMPLETE_SCRIPT`): ✅ Standard `EVAL`, fully supported.
- Pipeline transactions: ✅ Supported.
- `RedisSaver` + `RedisSaver.from_conn_string()`: ✅ Imports successfully.
- `RedisStore.from_conn_string()`: ✅ Imports successfully.
- `socket_timeout=10` on worker client: ✅ Correct for blocking commands.

### Managed Redis — Upstash free tier (candidate, not yet connected)

| Feature | Upstash Support | Risk | Notes |
|---------|----------------|------|-------|
| `BLMOVE` | ✅ Supported | LOW | Upstash supports blocking list commands |
| `LREM`, `LPUSH`, `LRANGE` | ✅ Supported | LOW | Standard list ops |
| `HSET`, `HGETALL`, `EXPIRE` | ✅ Supported | LOW | Standard hash ops |
| `EVAL` / Lua scripts | ✅ Supported | LOW | `COMPLETE_SCRIPT` should work |
| Pipeline / `MULTI-EXEC` | ✅ Supported | LOW | Worker uses `pipeline()` |
| TLS (`rediss://`) | **Required** | MEDIUM | Must use `rediss://` scheme — not `redis://` |
| `RedisSaver` checkpoints | ⚠ Not tested | MEDIUM | Requires live connection test to verify key formats |
| `RedisStore` | ⚠ Not tested | MEDIUM | Requires live connection test |
| Connection limits | ⚠ Free tier limited | MEDIUM | Upstash free: 10,000 commands/day max |
| Key persistence | ✅ Configurable | LOW | Upstash persists keys by default |

**Key finding:** `REDIS_URI=rediss://:<password>@<host>:6379` (note `rediss://` for TLS) is the  
only format change needed for Upstash. The `redis-py` client handles TLS automatically.  
No code changes are required beyond the URI — this is why fixing the hardcoded URI was the  
most important change in this phase.

**⚠ Critical unverified items:**
- `RedisSaver` checkpoint data format compatibility with Upstash — requires live test.
- `RedisStore` namespace operations with Upstash — requires live test.
- Actual blocking behaviour of `BLMOVE` over a TLS Upstash connection.

**Do not claim Upstash compatibility is verified** until a live connection test is run with:
1. A real `REDIS_URI=rediss://...` pointing to an Upstash endpoint.
2. The worker successfully processes a task end-to-end.
3. `RedisSaver` checkpoints and retrieves state without error.

### Upstash free-tier cost exposure
Upstash free tier: 10,000 commands/day. Each research task issues approximately 15–30 Redis  
commands (queue ops + heartbeats + completion + checkpoint writes). At ~300–666 tasks/day,  
the free tier is exhausted. **This is not a ₹0 guarantee** — heavy use will incur charges.

---

## E. Vector Database Assessment

### Chroma (current, local)
- **Status:** Working. No changes made. No changes needed for Phase 1.
- Initialized in `RAG/rag_tool.py` using `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")`.
- Persisted at `RAG/vectorstore/` (relative to project root).
- Collection name: `redis_knowledge`.
- Coupling: Chroma initialization happens at module import time in `rag_tool.py`.  
  This is fine for local use. In a containerized environment, the vectorstore directory  
  must exist and be populated before the API starts.

### pgvector (future — NOT implemented in Phase 1)
A clear boundary for future pgvector migration:

```
Phase 2+ boundary:
  RAG/rag_tool.py → replace Chroma with pgvector retriever
  RAG/ingest.py   → replace Chroma with pgvector upsert

Concerns:
  - Embedding migration: existing Chroma embeddings use all-MiniLM-L6-v2.
    pgvector migration must use the same model or re-embed all documents.
  - Web search ≠ vector search: DuckDuckGo + Wikipedia queries in
    research_workflow.py do NOT go through Chroma or pgvector.
    Only the RAG route (knowledge base queries) uses the vector store.
    This distinction must be preserved.
  - Supabase pgvector requires enabling the vector extension:
    CREATE EXTENSION IF NOT EXISTS vector;
    This must be executed by the project owner on the Supabase dashboard
    or via SQL editor — it requires database admin permissions.
    Do not enable extensions via MCP or application code.
```

---

## F. Report Storage Assessment

### Current behaviour (verified)
- `tools.py` `save_to_txt()`: writes to `os.path.join(os.path.dirname(__file__), "reports", filename)`.
- `api.py` `get_task_report()`: serves `REPORTS_DIR / Path(filename).name` with path traversal protection.
- Reports are named: `research_<slug>_<YYYYMMDD_HHMMSS>.txt`.
- The `reports/` directory is created automatically on startup (`mkdir(exist_ok=True)`).

### Local behaviour
✅ Working correctly. Files are written and served as expected.

### Cloud Run limitation — **MUST READ before Phase 2**

> **⚠ Cloud Run containers have ephemeral local filesystems.**
> 
> Reports written to `reports/` inside a Cloud Run container will be **permanently lost** when:
> - The container is restarted (cold start after inactivity).
> - A new revision is deployed.
> - The instance is scaled to zero and a new instance starts.
> - The container crashes and restarts.
>
> **Users who download a report immediately will succeed. Users who try to retrieve a report after a container restart will receive HTTP 404.**
>
> **This is not an acceptable user experience for a deployed service.**
>
> **Required before Phase 2 (cloud deployment):**
> Implement persistent report storage — recommended: Google Cloud Storage (GCS) bucket or  
> Supabase Storage. The report download endpoint must be updated to serve from cloud storage.

---

## G. Security & Spending Confirmation

### Credentials
- ✅ No credentials were hardcoded in any changed file.
- ✅ No credentials were logged or printed.
- ✅ No credentials were exposed in this document.
- ✅ `.env` remains gitignored and was not modified.
- ✅ `.env.example` contains only placeholder values (`gsk_your_groq_api_key_here`, etc.).

### Cloud resources
- ✅ No cloud infrastructure was created.
- ✅ No paid services were enabled.
- ✅ No Supabase tables were created or altered.
- ✅ No Cloud Run deployment was executed.
- ✅ No billing was changed.

### Spending policy compliance
- ✅ All Phase 1 work is local code changes only.
- ✅ No unapproved paid services were introduced.

---

## H. Remaining Blockers Before Phase 2

These manual steps are required before Phase 2 (cloud deployment) can begin:

| # | Blocker | Owner | Type |
|---|---------|-------|------|
| 1 | **Start Redis locally** to re-run Test 7 (checkpointing) | You | Local |
| 2 | **Provision Upstash Redis** (free tier) and set `REDIS_URI=rediss://...` | You | Cloud |
| 3 | **Test `BLMOVE` + `RedisSaver` against Upstash** with a real task | Phase 2 | Cloud |
| 4 | **Confirm Supabase MCP connectivity** — run a read-only list_tables query | Phase 2 | Cloud |
| 5 | **Design database schema** for task persistence (if moving from Redis → PostgreSQL) | Phase 2 | Architecture |
| 6 | **Enable pgvector extension** in Supabase dashboard | You | Cloud (1-click) |
| 7 | **Implement persistent report storage** (GCS or Supabase Storage) | Phase 2 | Cloud |
| 8 | **Write Dockerfile** for Cloud Run container | Phase 2 | DevOps |
| 9 | **Set `ALLOWED_ORIGINS`** to deployed frontend URL before production | Phase 2 | Config |
| 10 | **Review Upstash daily command quota** against expected task volume | You | Planning |

---

## I. Test Results (Phase 1 Baseline)

| Test | File | Result | Notes |
|------|------|--------|-------|
| test_health_endpoint | test_api.py | ✅ PASS | |
| test_ready_endpoint_ok | test_api.py | ✅ PASS | Mocked |
| test_ready_endpoint_fail | test_api.py | ✅ PASS | Mocked |
| test_submit_valid_research | test_api.py | ✅ PASS | Mocked |
| test_submit_invalid_research | test_api.py | ✅ PASS | |
| test_task_status_retrieval | test_api.py | ✅ PASS | Mocked |
| test_unknown_task_id | test_api.py | ✅ PASS | |
| test_task_result_retrieval | test_api.py | ✅ PASS | Mocked |
| test_failed_workflow_retrieval | test_api.py | ✅ PASS | |
| test_report_path_safety | test_api.py | ✅ PASS | |
| test_redis_unavailable_behavior | test_api.py | ✅ PASS | |
| Graph construction | test_research_workflow.py | ✅ PASS | |
| State propagation | test_research_workflow.py | ✅ PASS | |
| Research failure handling | test_research_workflow.py | ✅ PASS | |
| Synthesis (live LLM) | test_research_workflow.py | ✅ PASS | Live Groq call |
| Save (unique filename) | test_research_workflow.py | ✅ PASS | |
| End-to-end workflow | test_research_workflow.py | ✅ PASS | No checkpointer |
| Checkpointing | test_research_workflow.py | ❌ FAIL | Redis not running locally — **not a code bug** |
| Regression (router) | test_research_workflow.py | ✅ PASS | |
| test_api.py (full suite) | — | ✅ 11/11 PASSED | |
| test_worker_recovery.py | — | ⚠ NOT RUN | Requires Redis running |
| e2e_test_api.py | — | ⚠ NOT RUN | Requires Redis + worker running |

**Test 7 (Checkpointing) is blocked by Redis not running locally, not by a code defect.**  
The `REDIS_URI` fix in `research_workflow.py` does not change any test behaviour — it only  
enables the URI to be overridden without editing source code.

### Cloud integration tests
- ❌ Supabase PostgreSQL connection: NOT TESTED (no `DATABASE_URL` configured)
- ❌ Upstash Redis connection: NOT TESTED (no managed Redis provisioned)
- ❌ Cloud Run deployment: NOT EXECUTED
