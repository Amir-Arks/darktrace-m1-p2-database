"""Relational DB (PostgreSQL in production, SQLite for local dev) via SQLAlchemy."""
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .common import with_retry
from .config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    s = get_settings()
    kwargs = {"pool_pre_ping": True, "future": True}
    if s.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=5, max_overflow=10, pool_recycle=1800,
                      connect_args={"connect_timeout": int(s.connect_timeout)}
                      if s.database_url.startswith("postgresql") else {})
    engine = create_engine(s.database_url, **kwargs)

    def _probe():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine

    return with_retry("relational database", _probe, s.retries)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Session:
    """New Session. Caller must commit/close. Works as a FastAPI dependency body."""
    return _session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Commit on success, roll back on error, always close."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
