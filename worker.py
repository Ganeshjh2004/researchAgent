import logging
import os
import json
import time
import sys
import threading
import redis
from pathlib import Path

# Setup Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from research_workflow import run_research_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] WORKER: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("worker")

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URI, decode_responses=True, socket_timeout=10)

QUEUE_NAME = "research:queue"
PROCESSING_QUEUE = "research:processing"
WORKER_ID = f"worker-{os.getpid()}"
MAX_RETRIES = 2
HEARTBEAT_INTERVAL = 10
VISIBILITY_TIMEOUT = 35

# ── LUA SCRIPTS ───────────────────────────────────────────────────────────────

# Atomic completion script
# KEYS: [task_key, processing_queue]
# ARGV: [task_id, status, filename, summary, sources, error_msg]
COMPLETE_SCRIPT = """
local current_status = redis.call('HGET', KEYS[1], 'status')
if current_status == 'running' then
    if ARGV[2] == 'completed' then
        redis.call('HSET', KEYS[1], 'status', ARGV[2], 'filename', ARGV[3], 'summary', ARGV[4], 'sources', ARGV[5])
    else
        redis.call('HSET', KEYS[1], 'status', ARGV[2], 'error', ARGV[6])
    end
    redis.call('LREM', KEYS[2], 0, ARGV[1])
    return 1
else
    return 0
end
"""

complete_lua = redis_client.register_script(COMPLETE_SCRIPT)


# ── HEARTBEAT THREAD ─────────────────────────────────────────────────────────

class HeartbeatThread(threading.Thread):
    def __init__(self, task_id: str):
        super().__init__()
        self.task_id = task_id
        self.task_key = f"task:{task_id}"
        self.stop_event = threading.Event()
        self.daemon = True

    def run(self):
        while not self.stop_event.is_set():
            try:
                # Only heartbeat if still running
                if redis_client.hget(self.task_key, "status") == "running":
                    redis_client.hset(self.task_key, "last_heartbeat", str(time.time()))
            except Exception as e:
                log.warning(f"Heartbeat failed for task {self.task_id}: {e}")
            self.stop_event.wait(HEARTBEAT_INTERVAL)

    def stop(self):
        self.stop_event.set()


# ── RECOVERY LOGIC ────────────────────────────────────────────────────────────

def recover_abandoned_tasks():
    """Scan processing queue for tasks without recent heartbeats."""
    log.info("Scanning for abandoned tasks...")
    try:
        processing_tasks = redis_client.lrange(PROCESSING_QUEUE, 0, -1)
        for task_id in processing_tasks:
            task_key = f"task:{task_id}"
            task_data = redis_client.hgetall(task_key)
            
            # If task hash doesn't exist, remove from processing queue
            if not task_data:
                redis_client.lrem(PROCESSING_QUEUE, 0, task_id)
                continue
                
            status = task_data.get("status")
            if status != "running":
                # It's completed/failed but somehow stuck in processing queue
                redis_client.lrem(PROCESSING_QUEUE, 0, task_id)
                continue
                
            last_heartbeat_str = task_data.get("last_heartbeat")
            started_at_str = task_data.get("started_at")
            
            # Default to started_at if heartbeat hasn't happened yet
            last_seen_str = last_heartbeat_str or started_at_str
            if not last_seen_str:
                continue
                
            last_seen = float(last_seen_str)
            if time.time() - last_seen > VISIBILITY_TIMEOUT:
                # Abandoned!
                retries = int(task_data.get("retries", 0))
                if retries < MAX_RETRIES:
                    log.warning(f"Recovering abandoned task {task_id}. Attempt {retries + 1}/{MAX_RETRIES}.")
                    # Atomically remove from processing and push back to queue
                    # Use a transaction
                    pipeline = redis_client.pipeline()
                    pipeline.lrem(PROCESSING_QUEUE, 0, task_id)
                    pipeline.lpush(QUEUE_NAME, task_id)
                    pipeline.hset(task_key, mapping={
                        "status": "queued",
                        "retries": retries + 1
                    })
                    pipeline.execute()
                else:
                    log.error(f"Task {task_id} exceeded max retries. Marking as failed.")
                    complete_lua(
                        keys=[task_key, PROCESSING_QUEUE],
                        args=[task_id, "failed", "", "", "", "Max retries exceeded due to worker crashes."]
                    )
    except Exception as e:
        log.error(f"Error during recovery sweep: {e}")


# ── TASK EXECUTION ────────────────────────────────────────────────────────────

def execute_task(task_id: str):
    task_key = f"task:{task_id}"
    task_data = redis_client.hgetall(task_key)
    
    if not task_data:
        log.error(f"Task {task_id} missing metadata. Removing from processing.")
        redis_client.lrem(PROCESSING_QUEUE, 0, task_id)
        return
        
    query = task_data.get("query")
    
    # Mark as running
    redis_client.hset(task_key, mapping={
        "status": "running",
        "worker": WORKER_ID,
        "started_at": str(time.time()),
        "last_heartbeat": str(time.time())
    })
    
    log.info(f"Task {task_id}: Starting execution for query '{query}'")
    
    hb_thread = HeartbeatThread(task_id)
    hb_thread.start()

    try:
        # Isolated thread_id ensures safe LangGraph checkpoints
        state = run_research_workflow(
            user_request=query,
            thread_id=task_id,
            use_checkpointer=True
        )
        
        status = state.get("execution_status", "unknown")
        error_msg = state.get("error", "")
        
        if status == "failed" or error_msg:
            res = complete_lua(
                keys=[task_key, PROCESSING_QUEUE],
                args=[task_id, "failed", "", "", "", error_msg or "Unknown workflow failure"]
            )
            if res:
                log.error(f"Task {task_id}: Failed - {error_msg}")
            else:
                log.warning(f"Task {task_id}: Could not fail (state modified concurrently).")
        else:
            report = state.get("synthesized_report", "")
            lines = report.splitlines()
            if len(lines) > 300:
                cutoff_text = "\n".join(lines[:300])
                last_boundary = max(
                    cutoff_text.rfind(". "), cutoff_text.rfind("! "), cutoff_text.rfind("? "),
                    cutoff_text.rfind(".\n"), cutoff_text.rfind("!\n"), cutoff_text.rfind("?\n")
                )
                if last_boundary == -1 and cutoff_text and cutoff_text[-1] in ".!?":
                    last_boundary = len(cutoff_text) - 1
                    
                if last_boundary != -1:
                    summary = cutoff_text[:last_boundary + 1] + "..."
                else:
                    last_space = cutoff_text.rfind(" ")
                    summary = (cutoff_text[:last_space] if last_space != -1 else cutoff_text) + "..."
            else:
                summary = report

            sources = json.dumps(state.get("research_sources", []))
            filename = state.get("output_filename", "")
            
            res = complete_lua(
                keys=[task_key, PROCESSING_QUEUE],
                args=[task_id, "completed", filename, summary, sources, ""]
            )
            if res:
                log.info(f"Task {task_id}: Completed successfully.")
            else:
                log.warning(f"Task {task_id}: Could not complete (state modified concurrently).")
                
    except Exception as exc:
        log.error(f"Task {task_id}: Crashed with exception: {exc}")
        complete_lua(
            keys=[task_key, PROCESSING_QUEUE],
            args=[task_id, "failed", "", "", "", "Internal execution error."]
        )
    finally:
        hb_thread.stop()
        hb_thread.join()

def run_worker():
    log.info(f"Starting {WORKER_ID}. Listening to '{QUEUE_NAME}'...")
    try:
        if redis_client.ping():
            log.info("Redis connection established.")
    except Exception as e:
        log.error(f"Failed to connect to Redis: {e}")
        sys.exit(1)

    while True:
        # Sweep for abandoned tasks before blocking
        recover_abandoned_tasks()
        
        try:
            # Atomic pop from queue and push to processing list
            task_id = redis_client.blmove(QUEUE_NAME, PROCESSING_QUEUE, timeout=5, src="RIGHT", dest="LEFT")
            if task_id:
                execute_task(task_id)
        except redis.exceptions.ConnectionError:
            log.error("Redis connection lost. Retrying in 5s...")
            time.sleep(5)
        except redis.exceptions.TimeoutError:
            pass # Socket timeout expected
        except KeyboardInterrupt:
            log.info("Worker shutting down.")
            break
        except Exception as e:
            log.error(f"Worker loop error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_worker()
