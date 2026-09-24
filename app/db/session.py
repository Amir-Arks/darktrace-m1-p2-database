"""
SQLAlchemy Engine, Session Factory, and FastAPI Dependency.

Provides:
- engine: Central database engine connecting to PostgreSQL (or SQLite for offline tests)
- SessionLocal: sessionmaker factory for creating transactional database sessions
- get_db(): Context-managed session generator for FastAPI Dependency Injection
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings


# Configure connect_args and pool settings based on dialect
connect_args = {}
engine_kwargs = {}

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite requires check_same_thread=False for multithreaded FastAPI access
    connect_args["check_same_thread"] = False
else:
    # PostgreSQL connection pool configuration
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_pre_ping": True,  # Verifies connections before returning from pool
    })

# Central database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs
)

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
