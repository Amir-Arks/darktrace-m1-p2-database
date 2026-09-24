"""
SQLAlchemy Declarative Base with standard constraint naming conventions.

ALL TEAM MEMBERS MUST INHERIT FROM THIS BASE:
    from app.db.base import Base

    class MyModel(Base):
        __tablename__ = "my_table"
        ...

This ensures:
1. Unified metadata for Alembic migrations.
2. Predictable foreign-key and constraint names in PostgreSQL.
3. Clean cross-table relationship resolution without circular imports.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import MetaData, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Standard naming conventions for PostgreSQL constraints
# Ensures Alembic can generate reliable ALTER and DROP statements
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Common Declarative Base for all DarkTrace Pod 2 models.
    """
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


class TimestampMixin:
    """
    Standard UTC Timestamp mixin for models that track creation and updates.
    Conforms to DarkTrace UTC TIMESTAMPTZ convention.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
