import logging
import uuid
import sys
import json
import os
from typing import Optional, List, Union, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import redis

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from research_workflow import run_research_workflow

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] API: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api")

# ── App & Redis setup ─────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Research Agent API",
    description="Production API Core for LangGraph research workflow.",
    version="1.1.0",
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
    except Exception as e:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    raise HTTPException(status_code=503, detail="Redis ping failed")

@app.post("/api/v1/research", response_model=TaskStatusResponse, status_code=202)
def submit_research(request: ResearchRequest):
    """Submit a research job for background processing."""
    task_id = str(uuid.uuid4())
    
    try:
        # Initialize task in Redis
        redis_client.hset(f"task:{task_id}", mapping={
            "status": "queued",
            "query": request.query,
            "retries": "0"
        })
        # Set expiry of 7 days to clean up old tasks automatically
        redis_client.expire(f"task:{task_id}", 604800)
        
        # Enqueue the task
        redis_client.lpush("research:queue", task_id)
    except Exception as e:
        log.error(f"Failed to write to Redis: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize task. Storage unavailable.")

    return TaskStatusResponse(
        task_id=task_id,
        status="queued",
        query=request.query
    )

@app.get("/api/v1/research/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """Retrieve the status of a task."""
    task_data = redis_client.hgetall(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return TaskStatusResponse(
        task_id=task_id,
        status=task_data.get("status", "unknown"),
        query=task_data.get("query", "unknown"),
        error=task_data.get("error")
    )

@app.get("/api/v1/research/{task_id}/result", response_model=TaskResultResponse)
def get_task_result(task_id: str):
    """Retrieve the full research result metadata."""
    task_data = redis_client.hgetall(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
        
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

@app.get("/api/v1/research/{task_id}/report")
def get_task_report(task_id: str):
    """Retrieve the saved .txt report file."""
    task_data = redis_client.hgetall(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
        
    status = task_data.get("status")
    if status != "completed":
        raise HTTPException(status_code=400, detail=f"Task is {status}, report not available.")
        
    filename = task_data.get("filename")
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
