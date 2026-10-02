"""
test_phase2b_db_integration.py
───────────────────────────────
Comprehensive Phase 2B verification test suite:
  1. PostgreSQL connection succeeds.
  2. A test task can be created and read.
  3. Status transitions persist (queued -> running -> completed).
  4. Retry summary persists (retry count increment, failed state with error).
  5. Report metadata can be inserted and retrieved.
  6. Existing Redis queue behavior remains intact.
  7. Existing API polling, result, and report download continue working with DB fallback.
  8. Idempotency guard prevents reopening completed tasks.
  9. Strict isolated record cleanup (only records created by this test are deleted).
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import delete

from db import check_db_health, get_db_session, close_db
from models import ResearchTask, ResearchReport
from persistence import (
    create_task_record,
    get_task_record,
    update_task_running,
    update_task_retry,
    update_task_completed,
    update_task_failed,
    create_report_record,
    get_report_record,
    list_task_records,
)
from api import app, REPORTS_DIR

async def run_phase2b_verification():
    print("=" * 60)
    print("Phase 2B: PostgreSQL Application Integration Verification")
    print("=" * 60)
    client = TestClient(app)

    test_task_id = uuid.uuid4()
    retry_task_id = uuid.uuid4()
    test_report_file = REPORTS_DIR / f"test_{test_task_id}.txt"
    created_ids = [test_task_id, retry_task_id]

    try:
        # ── Item 1: PostgreSQL connection succeeds ─────────────────────────────
        print("\n[Check 1/8] Verifying PostgreSQL connection...")
        healthy = await check_db_health(timeout_seconds=30.0)
        assert healthy, "Database health check failed"
        print("  -> PostgreSQL connection healthy (SELECT 1 succeeded).")

        # ── Item 2: A test task can be created and read ────────────────────────
        print("\n[Check 2/8] Creating and reading durable task record...")
        task_rec = await create_task_record(
            task_id=test_task_id,
            query="Verify Phase 2B PostgreSQL integration",
            provider="groq",
            model="openai/gpt-oss-20b",
        )
        assert task_rec is not None, "Failed to create task record in PostgreSQL"
        assert task_rec["id"] == str(test_task_id), "Task ID mismatch"
        assert task_rec["status"] == "queued", f"Expected queued, got {task_rec['status']}"
        assert task_rec["retry_count"] == 0, "Initial retry count should be 0"

        read_rec = await get_task_record(test_task_id)
        assert read_rec is not None, "Failed to read created task record"
        assert read_rec["query"] == "Verify Phase 2B PostgreSQL integration"
        print(f"  -> Task created and read successfully: {test_task_id}")

        # ── Item 3: Status transitions persist & Idempotency ───────────────────
        print("\n[Check 3/8] Verifying status transitions and idempotency guards...")
        # queued -> running
        running_ok = await update_task_running(test_task_id)
        assert running_ok, "Failed to update task to running"
        rec_running = await get_task_record(test_task_id)
        assert rec_running["status"] == "running", f"Expected running, got {rec_running['status']}"
        assert rec_running["started_at"] is not None, "started_at was not recorded"
        print("  -> Transition 'running' persisted with started_at timestamp.")

        # running -> completed
        completed_ok = await update_task_completed(test_task_id)
        assert completed_ok, "Failed to update task to completed"
        rec_completed = await get_task_record(test_task_id)
        assert rec_completed["status"] == "completed", f"Expected completed, got {rec_completed['status']}"
        assert rec_completed["completed_at"] is not None, "completed_at was not recorded"
        print("  -> Transition 'completed' persisted with completed_at timestamp.")

        # Idempotency guard: duplicate delivery cannot reopen completed task
        reopen_attempt = await update_task_running(test_task_id)
        assert not reopen_attempt, "Idempotency failure: completed task was reopened!"
        reopen_retry = await update_task_retry(test_task_id, 2)
        assert not reopen_retry, "Idempotency failure: completed task was queued via retry!"
        rec_still_completed = await get_task_record(test_task_id)
        assert rec_still_completed["status"] == "completed", "Status was modified despite guard!"
        print("  -> Idempotency verified: completed task cannot be reopened or retried.")

        # ── Item 4: Retry summary and failure persist ──────────────────────────
        print("\n[Check 4/8] Verifying retry summary and failure persistence...")
        r_rec = await create_task_record(
            task_id=retry_task_id,
            query="Verify retry and failure flow",
        )
        assert r_rec is not None, "Failed to create retry test task"

        # Retry 1
        ret_ok = await update_task_retry(retry_task_id, 1)
        assert ret_ok, "Failed to update task retry count"
        rec_ret1 = await get_task_record(retry_task_id)
        assert rec_ret1["retry_count"] == 1, f"Expected retry_count 1, got {rec_ret1['retry_count']}"
        assert rec_ret1["status"] == "queued"

        # Retry 2
        ret_ok2 = await update_task_retry(retry_task_id, 2)
        assert ret_ok2, "Failed to update task retry count to 2"
        rec_ret2 = await get_task_record(retry_task_id)
        assert rec_ret2["retry_count"] == 2

        # Mark failed with reason
        fail_ok = await update_task_failed(retry_task_id, "Max retries exceeded due to worker crashes.")
        assert fail_ok, "Failed to mark task failed"
        rec_failed = await get_task_record(retry_task_id)
        assert rec_failed["status"] == "failed"
        assert rec_failed["error_message"] == "Max retries exceeded due to worker crashes."
        print("  -> Retry summary (count=2) and failed status persisted accurately.")

        # ── Item 5: Report metadata inserted and retrieved ────────────────────
        print("\n[Check 5/8] Verifying report metadata persistence in public.research_reports...")
        test_report_file.write_text("Phase 2B Test Report Content\nDetailed analysis results.")
        file_size = test_report_file.stat().st_size

        report_meta = await create_report_record(
            task_id=test_task_id,
            filename=test_report_file.name,
            storage_key=f"reports/{test_report_file.name}",
            size_bytes=file_size,
            storage_provider="local",
            content_type="text/plain",
        )
        assert report_meta is not None, "Failed to insert report metadata"
        assert report_meta["task_id"] == str(test_task_id)
        assert report_meta["filename"] == test_report_file.name
        assert report_meta["size_bytes"] == file_size
        assert report_meta["storage_provider"] == "local"

        read_report_meta = await get_report_record(test_task_id)
        assert read_report_meta is not None, "Failed to retrieve report metadata"
        assert read_report_meta["size_bytes"] == file_size
        print(f"  -> Report metadata persisted and retrieved: {read_report_meta['id']}")

        # ── Item 6: Existing Redis queue behavior remains intact ───────────────
        print("\n[Check 6/8] Verifying Redis queue operations...")
        import redis
        r_client = redis.Redis.from_url(os.getenv("REDIS_URI", "redis://localhost:6379"), decode_responses=True)
        test_q_key = "test:researchmate:queue"
        r_client.delete(test_q_key)
        r_client.lpush(test_q_key, "item_1", "item_2")
        assert r_client.llen(test_q_key) == 2
        popped = r_client.rpop(test_q_key)
        assert popped == "item_1"
        r_client.delete(test_q_key)
        print("  -> Redis queue operations confirmed functional.")

        # ── Item 7: API polling, result, and report endpoints with DB fallback ──
        print("\n[Check 7/8] Verifying API endpoints (status, result, report, history)...")
        # 7a. Task Status via DB fallback (not in Redis)
        resp_status = client.get(f"/api/v1/research/{test_task_id}")
        assert resp_status.status_code == 200, f"Expected 200, got {resp_status.status_code}"
        assert resp_status.json()["status"] == "completed"
        assert resp_status.json()["task_id"] == str(test_task_id)

        # 7b. Task Result via DB fallback
        resp_result = client.get(f"/api/v1/research/{test_task_id}/result")
        assert resp_result.status_code == 200, f"Expected 200, got {resp_result.status_code}"
        assert resp_result.json()["status"] == "completed"
        assert resp_result.json()["filename"] == test_report_file.name

        # 7c. Task Report download via DB metadata
        resp_report = client.get(f"/api/v1/research/{test_task_id}/report")
        assert resp_report.status_code == 200, f"Expected 200, got {resp_report.status_code}"
        assert "Phase 2B Test Report Content" in resp_report.text

        # 7d. History endpoint
        resp_history = client.get("/api/v1/research/history?limit=10")
        assert resp_history.status_code == 200, f"Expected 200, got {resp_history.status_code}"
        history_items = resp_history.json()
        assert any(item["task_id"] == str(test_task_id) for item in history_items)
        print("  -> API status, result, report download, and history endpoints all verified.")

    finally:
        # ── Item 8: Strict Isolated Cleanup ────────────────────────────────────
        print("\n[Check 8/8] Cleaning up isolated test records...")
        if test_report_file.exists():
            test_report_file.unlink()

        async with get_db_session() as session:
            if session is not None:
                for cid in created_ids:
                    await session.execute(
                        delete(ResearchReport).where(ResearchReport.task_id == cid)
                    )
                    await session.execute(
                        delete(ResearchTask).where(ResearchTask.id == cid)
                    )
        print("  -> Isolated test records purged from Supabase. No existing data touched.")

    await close_db()
    print("\n" + "=" * 60)
    print("ALL 8 VERIFICATION CHECKS COMPLETED AND PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_phase2b_verification())
