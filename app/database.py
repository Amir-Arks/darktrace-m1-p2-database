"""
app/database.py
Compatibility bridge re-exporting the central database engine and sessions from app.db.session.
Prevents duplicate engines or competing session factories across modules.
"""
from app.db.session import (
    engine,
    SessionLocal,
    get_db,
    get_session,
    verify_fk_enforcement,
    create_tables,
    db_info,
    IS_SQLITE,
    _apply_sqlite_pragmas,
)
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "get_session",
    "verify_fk_enforcement",
    "create_tables",
    "db_info",
    "IS_SQLITE",
    "DATABASE_URL",
    "_apply_sqlite_pragmas",
]
