"""
persistence.py
──────────────
Asynchronous persistence repository for ResearchMate.

Provides database access operations for:
  • ResearchTask creation, lookup, status updates, and retry tracking.
  • ResearchReport metadata storage and retrieval.
  • Idempotency guards (e.g. preventing completed tasks from being reopened).
  • Safe fallbacks and exception handling when PostgreSQL is unavailable.
  • Synchronous convenience wrappers for synchronous execution environments (e.g. worker).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import desc, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func

from db import get_db_session
from models import ResearchTask, ResearchReport

log = logging.getLogger("persistence")


def _to_uuid(val: Union[str, uuid.UUID]) -> Optional[uuid.UUID]:
    """Helper to convert string or UUID to uuid.UUID safely. Returns None on invalid format."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return None


# ── Async Task Operations ─────────────────────────────────────────────────────

async def create_task_record(
    task_id: Union[str, uuid.UUID],
    query: str,
    provider: str = "groq",
    model: str = "openai/gpt-oss-20b",
    owner_id: Optional[Union[str, uuid.UUID]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Creates a new research task in PostgreSQL with status 'queued'.
    Returns the task dictionary or None if database is disabled or operation fails.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            log.warning(f"Invalid UUID for create_task_record: {task_id}")
            return None
        o_uuid = _to_uuid(owner_id) if owner_id else None

        async with get_db_session() as session:
            if session is None:
                return None

            task = ResearchTask(
                id=t_uuid,
                owner_id=o_uuid,
                query=query,
                status="queued",
                provider=provider,
                model=model,
                retry_count=0,
            )
            session.add(task)
            await session.flush()
            await session.refresh(task)
            return task.to_dict()
    except SQLAlchemyError as e:
        log.error(f"Failed to create task record {task_id} in PostgreSQL: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error creating task record {task_id}: {e}")
        return None


async def get_task_record(task_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
    """
    Fetches a task record by UUID from PostgreSQL.
    Returns dictionary representation or None if not found or on error.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            return None
        async with get_db_session() as session:
            if session is None:
                return None

            stmt = select(ResearchTask).where(ResearchTask.id == t_uuid)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            return task.to_dict() if task else None
    except SQLAlchemyError as e:
        log.error(f"Failed to get task record {task_id} from PostgreSQL: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error getting task record {task_id}: {e}")
        return None


async def update_task_running(task_id: Union[str, uuid.UUID]) -> bool:
    """
    Updates a task's status to 'running' and sets started_at if not already set.
    Guards against reopening tasks that have already completed.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            return False
        async with get_db_session() as session:
            if session is None:
                return False

            # Idempotency guard: do not overwrite 'completed' status
            stmt = (
                update(ResearchTask)
                .where(ResearchTask.id == t_uuid, ResearchTask.status != "completed")
                .values(
                    status="running",
                    started_at=func.coalesce(ResearchTask.started_at, func.now()),
                    updated_at=func.now(),
                )
            )
            res = await session.execute(stmt)
            return res.rowcount > 0
    except SQLAlchemyError as e:
        log.error(f"Failed to update task {task_id} to running: {e}")
        return False
    except Exception as e:
        log.error(f"Unexpected error updating task {task_id} to running: {e}")
        return False


async def update_task_retry(task_id: Union[str, uuid.UUID], retry_count: int) -> bool:
    """
    Updates a task's retry count and resets status to 'queued'.
    Guards against reopening tasks that have already completed.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            return False
        async with get_db_session() as session:
            if session is None:
                return False

            stmt = (
                update(ResearchTask)
                .where(ResearchTask.id == t_uuid, ResearchTask.status != "completed")
                .values(
                    status="queued",
                    retry_count=retry_count,
                    updated_at=func.now(),
                )
            )
            res = await session.execute(stmt)
            return res.rowcount > 0
    except SQLAlchemyError as e:
        log.error(f"Failed to update task {task_id} retry: {e}")
        return False
    except Exception as e:
        log.error(f"Unexpected error updating task {task_id} retry: {e}")
        return False


async def update_task_completed(task_id: Union[str, uuid.UUID]) -> bool:
    """
    Marks a task as 'completed' and records completed_at timestamp.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            return False
        async with get_db_session() as session:
            if session is None:
                return False

            stmt = (
                update(ResearchTask)
                .where(ResearchTask.id == t_uuid)
                .values(
                    status="completed",
                    completed_at=func.now(),
                    updated_at=func.now(),
                    error_message=None,
                )
            )
            res = await session.execute(stmt)
            return res.rowcount > 0
    except SQLAlchemyError as e:
        log.error(f"Failed to update task {task_id} to completed: {e}")
        return False
    except Exception as e:
        log.error(f"Unexpected error updating task {task_id} to completed: {e}")
        return False


async def update_task_failed(task_id: Union[str, uuid.UUID], error_message: str) -> bool:
    """
    Marks a task as 'failed' and records the error message.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            return False
        async with get_db_session() as session:
            if session is None:
                return False

            stmt = (
                update(ResearchTask)
                .where(ResearchTask.id == t_uuid)
                .values(
                    status="failed",
                    completed_at=func.now(),
                    updated_at=func.now(),
                    error_message=error_message,
                )
            )
            res = await session.execute(stmt)
            return res.rowcount > 0
    except SQLAlchemyError as e:
        log.error(f"Failed to update task {task_id} to failed: {e}")
        return False
    except Exception as e:
        log.error(f"Unexpected error updating task {task_id} to failed: {e}")
        return False


# ── Async Report Operations ───────────────────────────────────────────────────

async def create_report_record(
    task_id: Union[str, uuid.UUID],
    filename: str,
    storage_key: str,
    size_bytes: int,
    storage_provider: str = "local",
    content_type: str = "text/plain",
) -> Optional[Dict[str, Any]]:
    """
    Stores report metadata in public.research_reports.
    Does NOT store report contents in PostgreSQL.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            log.warning(f"Invalid UUID for create_report_record: {task_id}")
            return None
        async with get_db_session() as session:
            if session is None:
                return None

            # Check if report already exists for this task (unique constraint)
            existing_stmt = select(ResearchReport).where(ResearchReport.task_id == t_uuid)
            existing_res = await session.execute(existing_stmt)
            existing = existing_res.scalar_one_or_none()
            if existing:
                existing.filename = filename
                existing.storage_key = storage_key
                existing.size_bytes = size_bytes
                existing.storage_provider = storage_provider
                existing.content_type = content_type
                await session.flush()
                await session.refresh(existing)
                return existing.to_dict()

            report = ResearchReport(
                id=uuid.uuid4(),
                task_id=t_uuid,
                filename=filename,
                storage_key=storage_key,
                size_bytes=size_bytes,
                storage_provider=storage_provider,
                content_type=content_type,
            )
            session.add(report)
            await session.flush()
            await session.refresh(report)
            return report.to_dict()
    except SQLAlchemyError as e:
        log.error(f"Failed to create report record for task {task_id} in PostgreSQL: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error creating report record for task {task_id}: {e}")
        return None


async def get_report_record(task_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
    """
    Retrieves report metadata by task UUID from public.research_reports.
    """
    try:
        t_uuid = _to_uuid(task_id)
        if t_uuid is None:
            return None
        async with get_db_session() as session:
            if session is None:
                return None

            stmt = select(ResearchReport).where(ResearchReport.task_id == t_uuid)
            result = await session.execute(stmt)
            report = result.scalar_one_or_none()
            return report.to_dict() if report else None
    except SQLAlchemyError as e:
        log.error(f"Failed to get report record for task {task_id}: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error getting report record for task {task_id}: {e}")
        return None


async def list_task_records(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Lists recent tasks ordered by created_at descending.
    """
    try:
        async with get_db_session() as session:
            if session is None:
                return []

            stmt = (
                select(ResearchTask)
                .order_by(desc(ResearchTask.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            return [t.to_dict() for t in tasks]
    except SQLAlchemyError as e:
        log.error(f"Failed to list task records: {e}")
        return []
    except Exception as e:
        log.error(f"Unexpected error listing task records: {e}")
        return []


# ── Synchronous Convenience Wrappers ──────────────────────────────────────────

def _run_sync(coro):
    """Executes an async persistence coroutine in a synchronous context safely."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If called inside an already running loop (e.g. pytest or another runner)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def sync_create_task_record(
    task_id: Union[str, uuid.UUID],
    query: str,
    provider: str = "groq",
    model: str = "openai/gpt-oss-20b",
    owner_id: Optional[Union[str, uuid.UUID]] = None,
) -> Optional[Dict[str, Any]]:
    return _run_sync(create_task_record(task_id, query, provider, model, owner_id))


def sync_get_task_record(task_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
    return _run_sync(get_task_record(task_id))


def sync_update_task_running(task_id: Union[str, uuid.UUID]) -> bool:
    return _run_sync(update_task_running(task_id))


def sync_update_task_retry(task_id: Union[str, uuid.UUID], retry_count: int) -> bool:
    return _run_sync(update_task_retry(task_id, retry_count))


def sync_update_task_completed(task_id: Union[str, uuid.UUID]) -> bool:
    return _run_sync(update_task_completed(task_id))


def sync_update_task_failed(task_id: Union[str, uuid.UUID], error_message: str) -> bool:
    return _run_sync(update_task_failed(task_id, error_message))


def sync_create_report_record(
    task_id: Union[str, uuid.UUID],
    filename: str,
    storage_key: str,
    size_bytes: int,
    storage_provider: str = "local",
    content_type: str = "text/plain",
) -> Optional[Dict[str, Any]]:
    return _run_sync(
        create_report_record(
            task_id, filename, storage_key, size_bytes, storage_provider, content_type
        )
    )


def sync_get_report_record(task_id: Union[str, uuid.UUID]) -> Optional[Dict[str, Any]]:
    return _run_sync(get_report_record(task_id))
