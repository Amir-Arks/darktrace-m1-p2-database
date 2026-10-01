"""
app/models/base.py
Shared declarative base for all SQLAlchemy models.
Works with both SQLite (dev) and PostgreSQL (prod).
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""
    pass
