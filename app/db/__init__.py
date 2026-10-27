"""
Database package: Base model, Session management, and dependencies
"""
from app.db.base import Base, TimestampMixin, POSTGRES_NAMING_CONVENTION
from app.db.session import (
    engine,
    SessionLocal,
    get_db,
    get_session,
    verify_fk_enforcement,
    create_tables,
    db_info,
    IS_SQLITE,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "POSTGRES_NAMING_CONVENTION",
    "engine",
    "SessionLocal",
    "get_db",
    "get_session",
    "verify_fk_enforcement",
    "create_tables",
    "db_info",
    "IS_SQLITE",
]
