"""
db.py
────
SQLAlchemy 2.x asynchronous database engine and session management.

Provides:
  • Lazy initialization of the AsyncEngine and async session factory.
  • URL normalization (converts postgresql:// to postgresql+asyncpg:// and
    safely handles passwords containing unencoded special characters).
  • Safe context manager for database sessions with automatic commit/rollback.
  • Health check utility for readiness and diagnostics.
  • Clean lifecycle disposal on application shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import os
import urllib.parse
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from config import settings

log = logging.getLogger("db")

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_engine_loop = None


def normalize_database_url(url_str: str) -> str:
    """
    Normalizes a PostgreSQL database URL for SQLAlchemy 2.x asyncpg.

    Handles:
      1. Scheme normalization: postgresql:// or postgres:// -> postgresql+asyncpg://
      2. Unencoded special characters (e.g. '@') in passwords by splitting credentials
         from the host using the last '@' delimiter and percent-encoding the password.
    """
    if not url_str or not url_str.strip():
        return ""

    url_str = url_str.strip()

    # Ensure asyncpg driver scheme
    if url_str.startswith("postgresql://"):
        url_str = "postgresql+asyncpg://" + url_str[len("postgresql://"):]
    elif url_str.startswith("postgres://"):
        url_str = "postgresql+asyncpg://" + url_str[len("postgres://"):]

    # Handle multiple '@' characters in URI if password contains unencoded '@'
    prefix, _, rest = url_str.partition("://")
    if rest.count("@") > 1:
        cred_part, _, host_part = rest.rpartition("@")
        user, _, raw_pwd = cred_part.partition(":")
        encoded_pwd = urllib.parse.quote(raw_pwd, safe="")
        url_str = f"{prefix}://{user}:{encoded_pwd}@{host_part}"

    return url_str


def get_engine() -> Optional[AsyncEngine]:
    """
    Returns the singleton AsyncEngine, creating it lazily if configured.
    Returns None if DATABASE_URL is not set.
    """
    global _engine, _session_factory, _engine_loop

    raw_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    if not raw_url or not raw_url.strip():
        return None

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _engine is not None and current_loop is not None and _engine_loop is not None:
        if current_loop != _engine_loop or _engine_loop.is_closed():
            _engine = None
            _session_factory = None

    if _engine is None:
        normalized_url = normalize_database_url(raw_url)
        try:
            _engine = create_async_engine(
                normalized_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_recycle=300,
            )
            _session_factory = async_sessionmaker(
                bind=_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            _engine_loop = current_loop
            log.info("Initialized PostgreSQL async engine with pool_pre_ping=True.")
        except Exception as e:
            log.error(f"Failed to initialize SQLAlchemy async engine: {e}")
            _engine = None
            _session_factory = None
            return None

    return _engine


def get_session_factory() -> Optional[async_sessionmaker[AsyncSession]]:
    """Returns the async sessionmaker singleton, initializing if necessary."""
    get_engine()
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[Optional[AsyncSession], None]:
    """
    Async context manager providing a scoped AsyncSession.
    Yields None if the database is not configured.
    Automatically commits on normal completion or rolls back on exception.
    """
    factory = get_session_factory()
    if factory is None:
        yield None
        return

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_health(timeout_seconds: float = 30.0) -> bool:
    """
    Runs a lightweight query (SELECT 1) to verify database connectivity.
    Returns True if healthy, False if unconfigured or unreachable.
    """
    engine = get_engine()
    if engine is None:
        return False

    try:
        import asyncio
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                return bool(row and row[0] == 1)
    except Exception as e:
        import traceback
        log.warning(f"Database health check failed: {e}")
        traceback.print_exc()
        return False


async def close_db() -> None:
    """Disposes the async engine connection pool cleanly on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.info("Disposed PostgreSQL async engine connection pool.")
