"""
app/models/login.py
SQLAlchemy model for the `login` table.
Dialect-agnostic — works on SQLite (dev) AND PostgreSQL (prod).

Type mapping:
    Uuid    → TEXT on SQLite  |  UUID  on PostgreSQL
    Boolean → INTEGER on SQLite  |  BOOLEAN on PostgreSQL
    JSON    → TEXT on SQLite  |  JSON/JSONB on PostgreSQL
    DateTime(timezone=True) → TEXT on SQLite  |  TIMESTAMPTZ on PostgreSQL
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, CheckConstraint, Index, text
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source import Source
    from app.models.crawl_job import CrawlJob


class Login(Base):
    """
    Authenticated users / operators who interact with DarkTrace.

    Relationships:
        registered_sources : sources this user registered   (1 → many)
        crawl_jobs         : crawl jobs triggered by this user (1 → many)
    """
    __tablename__ = "login"

    # ── Primary key ───────────────────────────────────────────────────────
    # Uuid: stored as native UUID on PostgreSQL, TEXT on SQLite
    login_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate UUID primary key.",
    )

    # ── Identity ──────────────────────────────────────────────────────────
    username: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True,
        comment="Unique login handle.",
    )
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True,
        comment="Unique contact e-mail.",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Hashed credential (bcrypt/argon2). NEVER store plaintext.",
    )

    # ── Role / access level ───────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="analyst",
        comment="Access level: admin | analyst | viewer | api_service.",
    )

    # ── Status ────────────────────────────────────────────────────────────
    # Boolean: SQLite → 0/1 INTEGER  |  PostgreSQL → native BOOLEAN
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="False = soft-deleted / suspended account.",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of the most recent successful authentication.",
    )

    # ── Audit timestamps ──────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    registered_sources: Mapped[List["Source"]] = relationship(
        "Source",
        back_populates="registrar",
        foreign_keys="[Source.registered_by]",
        lazy="select",
    )
    crawl_jobs: Mapped[List["CrawlJob"]] = relationship(
        "CrawlJob",
        back_populates="triggerer",
        foreign_keys="[CrawlJob.triggered_by]",
        lazy="select",
    )

    # ── Table-level constraints & indexes ─────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'analyst', 'viewer', 'api_service')",
            name="chk_login_role",
        ),
        Index("idx_login_username",  "username"),
        Index("idx_login_email",     "email"),
        Index("idx_login_role",      "role"),
        Index("idx_login_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<Login id={self.login_id} "
            f"username={self.username!r} role={self.role!r}>"
        )
