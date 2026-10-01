"""
app/database.py
═══════════════════════════════════════════════════════════════════════════════
M2 — Database Layer  (Anil Kumar)
───────────────────────────────────────────────────────────────────────────────
Provides:
  • engine       — SQLAlchemy Engine (SQLite dev OR PostgreSQL prod)
  • SessionLocal — session factory for M3 backend to use
  • get_session()— context-manager session (use in scripts / tests)
  • create_tables()       — create schema from models (SQLite dev only)
  • verify_fk_enforcement()— startup check that FK constraints are active

M3 (Backend) handoff
─────────────────────
  Import from this module:
      from app.database import SessionLocal, engine, verify_fk_enforcement

  For FastAPI dependency injection in M3, add this to your dependencies.py:

      from sqlalchemy.orm import Session
      from app.database import SessionLocal
      from typing import Generator

      def get_db() -> Generator[Session, None, None]:
          db = SessionLocal()
          try:
              yield db
              db.commit()
          except Exception:
              db.rollback()
              raise
          finally:
              db.close()

Database selection (set in .env):
  SQLite   →  DATABASE_URL=sqlite:///./darktrace.db          (default / dev)
  PostgreSQL→  DATABASE_URL=postgresql+psycopg2://user:pw@host:5432/db  (prod)
═══════════════════════════════════════════════════════════════════════════════

SQLITE FK ENFORCEMENT — 3-LAYER SOLUTION
─────────────────────────────────────────
SQLite does NOT enforce FKs by default. Every connection needs:
    PRAGMA foreign_keys = ON

Layer 1 — "connect" event  : fires when a NEW raw connection is created.
Layer 2 — "checkout" event : fires every time a connection leaves the pool.
           This is the critical layer — recycled connections lose the PRAGMA
           without this hook.
Layer 3 — verify_fk_enforcement() : reads PRAGMA at startup and raises
           RuntimeError if FKs are not ON. Call once before serving traffic.
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy import pool as sa_pool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Database URL — read from environment, default to SQLite for dev
# ─────────────────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./darktrace.db",
)

IS_SQLITE   = DATABASE_URL.startswith("sqlite")
IS_POSTGRES = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Engine
# ─────────────────────────────────────────────────────────────────────────────
if IS_SQLITE:
    engine: Engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        # StaticPool: every thread shares one connection → PRAGMA always active
        poolclass=sa_pool.StaticPool,
        echo=False,
    )
else:
    # PostgreSQL — FK constraints are always enforced natively
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # discard dead connections
        pool_size=10,
        max_overflow=20,
        echo=False,
    )

# ─────────────────────────────────────────────────────────────────────────────
# 3. SQLite FK Enforcement — Layer 1: new connection
# ─────────────────────────────────────────────────────────────────────────────
def _apply_sqlite_pragmas(dbapi_connection) -> None:
    """Apply all required SQLite PRAGMAs to a raw dbapi connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")     # ← enforce FK constraints
        cursor.execute("PRAGMA journal_mode = WAL")    # better read concurrency
        cursor.execute("PRAGMA synchronous = NORMAL")  # safe + fast
    finally:
        cursor.close()


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):
        """Layer 1: runs once when a brand-new physical connection is created."""
        _apply_sqlite_pragmas(dbapi_conn)
        logger.debug("SQLite PRAGMA foreign_keys=ON applied (new connection).")

# ─────────────────────────────────────────────────────────────────────────────
# 4. SQLite FK Enforcement — Layer 2: every pool checkout  ← CRITICAL
# ─────────────────────────────────────────────────────────────────────────────
    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, _record, _proxy):
        """
        Layer 2: runs EVERY TIME a connection leaves the pool.
        Without this, recycled connections silently lose the PRAGMA.
        """
        _apply_sqlite_pragmas(dbapi_conn)

# ─────────────────────────────────────────────────────────────────────────────
# 5. SQLite FK Enforcement — Layer 3: startup verification
# ─────────────────────────────────────────────────────────────────────────────
def verify_fk_enforcement() -> None:
    """
    Layer 3 — read PRAGMA foreign_keys and raise RuntimeError if it is not 1.

    Call once at application startup (before serving any request).
    PostgreSQL is skipped automatically — it always enforces FKs.

    Example (plain script):
        from app.database import verify_fk_enforcement
        verify_fk_enforcement()

    Example (M3 FastAPI lifespan):
        @asynccontextmanager
        async def lifespan(app):
            verify_fk_enforcement()
            yield
    """
    if not IS_SQLITE:
        logger.info("FK check skipped — PostgreSQL enforces FKs natively.")
        return

    with engine.connect() as conn:
        row = conn.execute(text("PRAGMA foreign_keys")).fetchone()
        value = row[0] if row else None

    if value != 1:
        raise RuntimeError(
            f"SQLite FK enforcement is OFF (PRAGMA foreign_keys = {value!r}).\n"
            "The 'connect'/'checkout' event hooks in app/database.py are not firing.\n"
            "crawl_job.triggered_by and crawl_job.source_id will NOT be enforced."
        )

    logger.info("✅ SQLite FK enforcement confirmed — PRAGMA foreign_keys = ON.")

# ─────────────────────────────────────────────────────────────────────────────
# 6. Session factory  (M3 imports SessionLocal)
# ─────────────────────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ─────────────────────────────────────────────────────────────────────────────
# 7. Context-manager session — use in scripts / tests / Alembic seeds
# ─────────────────────────────────────────────────────────────────────────────
@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context-manager that yields a Session, commits on success, rolls back
    on any exception, and always closes the session.

    Usage (scripts / seed data / tests):
        from app.database import get_session
        with get_session() as db:
            db.add(some_object)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# ─────────────────────────────────────────────────────────────────────────────
# 8. Table creation — SQLite dev / CI only
# ─────────────────────────────────────────────────────────────────────────────
def create_tables() -> None:
    """
    Create all tables registered on Base.metadata.

    SQLite dev  : call this once at startup or in CI setup.
    PostgreSQL  : use  alembic upgrade head  instead.
    """
    from app.models import Base   # deferred import — avoids circular deps
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created on %s.", "SQLite" if IS_SQLITE else "PostgreSQL")

# ─────────────────────────────────────────────────────────────────────────────
# 9. Utility
# ─────────────────────────────────────────────────────────────────────────────
def db_info() -> str:
    """Return a human-readable string describing the active database."""
    label = "SQLite (development)" if IS_SQLITE else "PostgreSQL (production)"
    return f"[M2] Database: {label}  |  {DATABASE_URL}"
