import logging
import uuid
import sys
import json
import os
from contextlib import asynccontextmanager
from typing import Optional, List, Union, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import redis

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from research_workflow import run_research_workflow
from db import close_db
from persistence import (
    create_task_record,
    get_task_record,
    update_task_failed,
    get_report_record,
    list_task_records,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] API: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api")


# ── Lifespan & App Setup ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_db()


app = FastAPI(
    title="AI Research Agent API",
    description="Production API Core for LangGraph research workflow.",
    version="1.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Vite dev server (5173) and preview server (4173) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URI, decode_responses=True)

REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ── Models ────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str

class ReadyResponse(BaseModel):
    status: str
    redis: str

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    query: str
    error: Optional[str] = None

class SourceItem(BaseModel):
    name: str
    url: Optional[str] = None

class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    query: str
    filename: Optional[str] = None
    summary: Optional[str] = None
    sources: List[Union[SourceItem, str]] = Field(default_factory=list)
    error: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Basic process health."""
    return {"status": "ok", "version": "1.1.0"}

@app.get("/ready", response_model=ReadyResponse)
def ready_check():
    """Dependency readiness (Redis)."""
    try:
        if redis_client.ping():
            return {"status": "ok", "redis": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    raise HTTPException(status_code=503, detail="Redis ping failed")

@app.post("/api/v1/research", response_model=TaskStatusResponse, status_code=202)
async def submit_research(request: ResearchRequest):
    """
    Submit a research job for background processing.
    1. Generates UUID task ID.
    2. Creates durable PostgreSQL record (if configured).
    3. Enqueues job via Redis queue.
    4. Preserves HTTP 202 response contract.
    """
    task_id = str(uuid.uuid4())
    
    # 1. Create durable PostgreSQL task record
    try:
        await create_task_record(task_id=task_id, query=request.query)
    except Exception as e:
        log.warning(f"Could not write task {task_id} to PostgreSQL: {e}")

    # 2. Enqueue in Redis
    try:
        redis_client.hset(f"task:{task_id}", mapping={
            "status": "queued",
            "query": request.query,
            "retries": "0"
        })
        redis_client.expire(f"task:{task_id}", 604800)
        redis_client.lpush("research:queue", task_id)
    except Exception as e:
        log.error(f"Failed to write to Redis: {e}")
        # Attempt to mark failed in PostgreSQL if Redis enqueue fails
        try:
            await update_task_failed(task_id, "Failed to enqueue task to Redis")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to initialize task. Storage unavailable.")

    return TaskStatusResponse(
        task_id=task_id,
        status="queued",
        query=request.query
    )

@app.get("/api/v1/research/history", response_model=List[TaskStatusResponse])
async def get_task_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Retrieve database-backed task history."""
    tasks = await list_task_records(limit=limit, offset=offset)
    return [
        TaskStatusResponse(
            task_id=str(t["id"]),
            status=t["status"],
            query=t["query"],
            error=t.get("error_message"),
        )
        for t in tasks
    ]

@app.get("/api/v1/research/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Retrieve the status of a task.
    Checks Redis first (hot cache), then falls back to PostgreSQL (system of record).
    """
    task_data = redis_client.hgetall(f"task:{task_id}")
    if task_data:
        return TaskStatusResponse(
            task_id=task_id,
            status=task_data.get("status", "unknown"),
            query=task_data.get("query", "unknown"),
            error=task_data.get("error")
        )
        
    # Fallback to PostgreSQL
    db_task = await get_task_record(task_id)
    if db_task:
        return TaskStatusResponse(
            task_id=str(db_task["id"]),
            status=db_task.get("status", "unknown"),
            query=db_task.get("query", "unknown"),
            error=db_task.get("error_message")
        )

    raise HTTPException(status_code=404, detail="Task not found")

@app.get("/api/v1/research/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(task_id: str):
    """
    Retrieve the full research result metadata.
    Checks Redis first, then falls back to PostgreSQL.
    """
    task_data = redis_client.hgetall(f"task:{task_id}")
    if task_data:
        sources_raw = task_data.get("sources")
        sources = json.loads(sources_raw) if sources_raw else []

        return TaskResultResponse(
            task_id=task_id,
            status=task_data.get("status", "unknown"),
            query=task_data.get("query", "unknown"),
            filename=task_data.get("filename"),
            summary=task_data.get("summary"),
            sources=sources,
            error=task_data.get("error")
        )

    # Fallback to PostgreSQL
    db_task = await get_task_record(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    db_report = await get_report_record(task_id)
    return TaskResultResponse(
        task_id=str(db_task["id"]),
        status=db_task.get("status", "unknown"),
        query=db_task.get("query", "unknown"),
        filename=db_report.get("filename") if db_report else None,
        summary=None,
        sources=[],
        error=db_task.get("error_message")
    )

@app.get("/api/v1/research/{task_id}/report")
async def get_task_report(task_id: str):
    """
    Retrieve the saved .txt report file.
    Checks Redis and PostgreSQL metadata for filename, then serves from REPORTS_DIR.
    """
    task_data = redis_client.hgetall(f"task:{task_id}")
    status = None
    filename = None

    if task_data:
        status = task_data.get("status")
        filename = task_data.get("filename")
    else:
        db_task = await get_task_record(task_id)
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        status = db_task.get("status")
        db_report = await get_report_record(task_id)
        if db_report:
            filename = db_report.get("filename")

    if status != "completed":
        raise HTTPException(status_code=400, detail=f"Task is {status}, report not available.")
        
    if not filename:
        raise HTTPException(status_code=404, detail="Filename not found in task metadata.")
        
    # Prevent path traversal vulnerabilities by enforcing basename and restricting to reports dir
    safe_filename = Path(filename).name
    file_path = REPORTS_DIR / safe_filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Report file not found on disk.")
        
    return FileResponse(
        path=file_path,
        media_type="text/plain",
        filename=safe_filename
    )
