"""
SQLAlchemy Engine, Session Factory, and FastAPI Dependency.

Provides:
- engine: Central database engine connecting to PostgreSQL (or SQLite for offline tests)
- SessionLocal: sessionmaker factory for creating transactional database sessions
- get_db(): Context-managed session generator for FastAPI Dependency Injection
- get_session(): Context manager for scripts, background jobs, and tests
- verify_fk_enforcement(): Startup verification helper for SQLite foreign keys
- create_tables(): Fast schema creator for local testing
- db_info(): Diagnostic description of active database
"""
import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import pool as sa_pool
from app.core.config import settings

logger = logging.getLogger("darktrace.db")

IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Configure connect_args and pool settings based on dialect
connect_args = {}
engine_kwargs = {}

if IS_SQLITE:
    connect_args["check_same_thread"] = False
    if ":memory:" in settings.DATABASE_URL or "mode=memory" in settings.DATABASE_URL:
        engine_kwargs["poolclass"] = sa_pool.StaticPool
else:
    # PostgreSQL connection pool configuration
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_pre_ping": True,  # Discards dead connections
    })

# Central database engine
engine: Engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs
)


def _apply_sqlite_pragmas(dbapi_connection) -> None:
    """Apply required SQLite PRAGMAs to a raw dbapi connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
    finally:
        cursor.close()


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _on_sqlite_connect(dbapi_conn, _record):
        """Layer 1: Enforce SQLite PRAGMA foreign_keys=ON on new connection."""
        _apply_sqlite_pragmas(dbapi_conn)

    @event.listens_for(engine, "checkout")
    def _on_sqlite_checkout(dbapi_conn, _record, _proxy):
        """Layer 2: Re-enforce PRAGMA foreign_keys=ON on every pool checkout."""
        _apply_sqlite_pragmas(dbapi_conn)


def verify_fk_enforcement() -> None:
    """Verify that foreign keys are enforced by the database."""
    if not IS_SQLITE:
        logger.info("FK check skipped — PostgreSQL enforces foreign keys natively.")
        return

    with engine.connect() as conn:
        row = conn.execute(text("PRAGMA foreign_keys")).fetchone()
        value = row[0] if row else None

    if value != 1:
        raise RuntimeError(
            f"SQLite FK enforcement is OFF (PRAGMA foreign_keys = {value!r})."
        )
    logger.info("SQLite FK enforcement verified (PRAGMA foreign_keys = ON).")


# Thread-local session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    Guarantees session cleanup upon request completion.

    Usage in FastAPI route:
        @router.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context-manager that yields a Session, commits on success, rolls back
    on any exception, and always closes the session.

    Usage:
        with get_session() as db:
            db.add(item)
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


def create_tables() -> None:
    """Create all tables registered on Base.metadata (for testing/dev)."""
    from app.db.base import Base
    Base.metadata.create_all(bind=engine)


def db_info() -> str:
    """Return a diagnostic string describing the active database."""
    masked = str(engine.url)
    label = "SQLite" if IS_SQLITE else "PostgreSQL"
    return f"[DarkTrace DB] {label} | {masked}"
