"""
app/api/deps.py
FastAPI dependency providers for Database sessions.
"""
from typing import Generator
from sqlalchemy.orm import Session
from app.database import get_session


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides an active DB session and handles cleanup."""
    with get_session() as session:
        yield session
