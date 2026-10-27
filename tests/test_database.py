"""
Unit and integration tests for common database infrastructure.
Verifies engine creation, session factory, FastAPI get_db dependency, and metadata conventions.
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.base import Base, POSTGRES_NAMING_CONVENTION
from app.db.session import get_db


def test_settings_configuration():
    """Verify settings are properly populated and contain essential database attributes."""
    assert hasattr(settings, "DATABASE_URL")
    assert settings.DATABASE_URL is not None
    assert hasattr(settings, "DB_POOL_SIZE")
    assert hasattr(settings, "DB_MAX_OVERFLOW")
    assert hasattr(settings, "DB_POOL_TIMEOUT")


def test_base_metadata_naming_conventions():
    """Verify standard constraint naming conventions are configured on Base.metadata."""
    conventions = Base.metadata.naming_convention
    assert conventions is not None
    assert "pk" in conventions
    assert "fk" in conventions
    assert "uq" in conventions
    assert "ck" in conventions
    assert "ix" in conventions

    # Assert exact pattern matches
    assert conventions["pk"] == "pk_%(table_name)s"
    assert conventions["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"


def test_session_lifecycle_with_test_engine():
    """Verify SQLAlchemy engine and session lifecycle (connect, execute, commit, rollback)."""
    test_engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # 1. Query execution
    with test_engine.connect() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        assert res == 1

    # 2. Session creation and transaction
    session = TestingSession()
    try:
        val = session.execute(text("SELECT 42")).scalar()
        assert val == 42
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_fastapi_get_db_generator():
    """Verify FastAPI get_db dependency yields a valid session and closes it on completion."""
    from unittest.mock import patch
    with patch.object(Session, "close") as mock_close:
        gen = get_db()
        db_session = next(gen)

        assert isinstance(db_session, Session)
        assert not mock_close.called, "Session should remain open during request"

        # Closing generator simulates FastAPI request completion
        with pytest.raises(StopIteration):
            next(gen)

        assert mock_close.called, "Session.close() must be called in finally block"


def test_alembic_configuration_validity():
    """Verify alembic.ini and migrations environment can be read by Alembic."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    assert script is not None
    assert script.dir == "migrations"
