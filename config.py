"""
config.py
─────────
Centralised, environment-driven configuration for ResearchMate.

All modules should import from here rather than calling os.getenv()
directly.  This provides:

  • A single source of truth for every env variable the app uses.
  • Early failure with an actionable error when a required variable is missing.
  • Separation between local-development defaults and cloud-production values.

Usage
-----
    from config import settings

    # Read a value
    redis_uri = settings.REDIS_URI

Configuration sources (in order of priority)
---------------------------------------------
  1. Actual environment variables (set by the OS, docker-compose, Cloud Run, etc.)
  2. A `.env` file loaded by python-dotenv at application startup.
  3. Built-in defaults defined below (only for optional variables).

Environment Variables Reference
--------------------------------
  Required:
    GROQ_API_KEY          — Groq API key for LLM access (BYOK)

  Optional (safe defaults allow local development without configuration):
    REDIS_URI             — Redis connection URL
                            Local:   redis://localhost:6379
                            Upstash: rediss://<user>:<password>@<host>:<port>
                            Default: redis://localhost:6379

    DATABASE_URL          — PostgreSQL connection URL (Supabase or local)
                            Local:   postgresql+asyncpg://user:pass@localhost:5432/researchmate
                            Supabase: postgresql+asyncpg://postgres:<pass>@db.<ref>.supabase.co:5432/postgres
                            Default: (empty — PostgreSQL not required for local Redis-only operation)

    CHROMA_PERSIST_DIR    — Absolute or relative path to the Chroma vector store directory.
                            Default: RAG/vectorstore (relative to project root)

    REPORTS_DIR           — Directory where .txt research reports are written.
                            Default: reports (relative to project root)
                            ⚠ Cloud Run warning: this path is ephemeral on stateless containers.
                              Reports will be lost on restart/redeployment without persistent storage.

    APP_ENV               — Runtime environment label. Affects logging and debug behaviour.
                            Values: local | staging | production
                            Default: local

    ALLOWED_ORIGINS       — Comma-separated list of CORS origins.
                            Default: http://localhost:5173,http://localhost:4173

Notes
-----
  • Never hardcode credentials in this file or any other source file.
  • Never commit .env to version control (.gitignore already excludes it).
  • Use .env.example as the canonical documentation of available variables.
  • Supabase connection string format uses ?pgbouncer=true for pooled connections.
    Use direct (port 5432) connections for local dev and migration tooling.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env before reading any variable ────────────────────────────────────

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")


# ── Configuration class ───────────────────────────────────────────────────────

class _Settings:
    """
    Reads, validates, and exposes all application configuration.

    Instantiated once at module level; import `settings` to use it.
    """

    # ── Required variables ────────────────────────────────────────────────────

    @property
    def GROQ_API_KEY(self) -> str:
        value = os.getenv("GROQ_API_KEY", "").strip()
        if not value:
            raise EnvironmentError(
                "GROQ_API_KEY is not set.\n"
                "Add it to your .env file:  GROQ_API_KEY=gsk_your_key_here\n"
                "Or set it as an environment variable before starting the application."
            )
        return value

    # ── Redis ─────────────────────────────────────────────────────────────────

    @property
    def REDIS_URI(self) -> str:
        """
        Redis connection URL.

        Local:   redis://localhost:6379
        Upstash: rediss://<user>:<password>@<host>:<port>

        Upstash requires TLS (rediss://). The existing redis-py client
        (redis.Redis.from_url) handles TLS automatically when the scheme
        is 'rediss://'.  No code changes are needed beyond setting this URL.
        """
        return os.getenv("REDIS_URI", "redis://localhost:6379")

    # ── PostgreSQL / Supabase ─────────────────────────────────────────────────

    @property
    def DATABASE_URL(self) -> str | None:
        """
        PostgreSQL connection URL for SQLAlchemy.

        Returns None if not configured — PostgreSQL is not required for the
        current Redis-only persistence model.  Set this when Supabase
        PostgreSQL is ready for use.

        Supported formats:
          postgresql+asyncpg://user:password@host:5432/dbname
          postgresql+psycopg2://user:password@host:5432/dbname
        """
        return os.getenv("DATABASE_URL") or None

    @property
    def database_url_is_configured(self) -> bool:
        return bool(self.DATABASE_URL)

    # ── Chroma ────────────────────────────────────────────────────────────────

    @property
    def CHROMA_PERSIST_DIR(self) -> Path:
        """
        Absolute path to the local Chroma vector store directory.

        Defaults to RAG/vectorstore inside the project root.
        Override via CHROMA_PERSIST_DIR environment variable.
        """
        raw = os.getenv("CHROMA_PERSIST_DIR", "")
        if raw:
            return Path(raw)
        return _BASE_DIR / "RAG" / "vectorstore"

    # ── Report storage ────────────────────────────────────────────────────────

    @property
    def REPORTS_DIR(self) -> Path:
        """
        Local directory where .txt research reports are written.

        ⚠ Cloud Run limitation: Container filesystems are ephemeral.
          Reports written here will NOT survive container restarts or
          redeployments.  Persistent cloud object storage (e.g. GCS, Supabase
          Storage) must be implemented before relying on report downloads in
          a cloud environment.
        """
        raw = os.getenv("REPORTS_DIR", "")
        if raw:
            return Path(raw)
        return _BASE_DIR / "reports"

    # ── Application ───────────────────────────────────────────────────────────

    @property
    def APP_ENV(self) -> str:
        """
        Runtime environment.  Values: local | staging | production.
        """
        return os.getenv("APP_ENV", "local").lower()

    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        """
        CORS allowed origins.  Comma-separated in env var.

        Default: Vite dev server (5173) and preview server (4173).
        In production, set this to your actual frontend domain.
        """
        raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173")
        return [o.strip() for o in raw.split(",") if o.strip()]

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def describe(self) -> dict:
        """
        Return a safe summary of the current configuration.

        Redacts credential values so this can be logged at startup without
        exposing secrets.
        """
        def _redact(value: str | None) -> str:
            if not value:
                return "(not set)"
            # Show scheme + host only for URLs; mask passwords
            if "://" in value:
                try:
                    from urllib.parse import urlparse
                    p = urlparse(value)
                    masked = f"{p.scheme}://***@{p.hostname}:{p.port}{p.path}"
                    return masked
                except Exception:
                    return "***"
            # For API keys show first 8 chars + mask the rest
            if len(value) > 8:
                return value[:8] + "***"
            return "***"

        groq_key = os.getenv("GROQ_API_KEY", "")
        redis_uri = os.getenv("REDIS_URI", "redis://localhost:6379")
        db_url = os.getenv("DATABASE_URL", "")

        return {
            "APP_ENV": self.APP_ENV,
            "GROQ_API_KEY": _redact(groq_key),
            "REDIS_URI": _redact(redis_uri),
            "DATABASE_URL": _redact(db_url) if db_url else "(not set — PostgreSQL disabled)",
            "CHROMA_PERSIST_DIR": str(self.CHROMA_PERSIST_DIR),
            "REPORTS_DIR": str(self.REPORTS_DIR),
            "ALLOWED_ORIGINS": self.ALLOWED_ORIGINS,
        }


# ── Module-level singleton ────────────────────────────────────────────────────

settings = _Settings()


# ── CLI self-check ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    print("ResearchMate — Configuration Check")
    print("=" * 50)

    try:
        cfg = settings.describe()
        print(json.dumps(cfg, indent=2))
        print()

        # Validate required key
        _ = settings.GROQ_API_KEY
        print("[OK] GROQ_API_KEY  is set")

        # Optional checks
        if settings.database_url_is_configured:
            print("[OK] DATABASE_URL   is set (PostgreSQL enabled)")
        else:
            print("[--] DATABASE_URL   not set (PostgreSQL disabled -- Redis-only mode)")

        print(f"[OK] REDIS_URI      {settings.REDIS_URI}")
        print(f"[OK] APP_ENV        {settings.APP_ENV}")
        print(f"[OK] REPORTS_DIR    {settings.REPORTS_DIR}")
        print(f"[OK] CHROMA_DIR     {settings.CHROMA_PERSIST_DIR}")
        print()
        print("Configuration check passed.")
    except EnvironmentError as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
