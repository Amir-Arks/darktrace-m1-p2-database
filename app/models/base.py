"""
app/models/base.py
Shared declarative base for all SQLAlchemy models.
Re-exports the single, unified Base from app.db.base with PostgreSQL constraint naming conventions.
"""
from app.db.base import Base, TimestampMixin, POSTGRES_NAMING_CONVENTION

__all__ = ["Base", "TimestampMixin", "POSTGRES_NAMING_CONVENTION"]
