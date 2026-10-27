"""
app/models/source.py
SQLAlchemy model for the `source` table.
Dialect-agnostic — works on SQLite (dev) AND PostgreSQL (prod).

Type mapping:
    Uuid    → TEXT on SQLite  |  UUID       on PostgreSQL
    JSON    → TEXT on SQLite  |  JSON/JSONB on PostgreSQL
    Boolean → 0/1  on SQLite  |  BOOLEAN    on PostgreSQL
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    String, Boolean, DateTime, Integer, Text,
    CheckConstraint, Index, ForeignKey, text
)
from sqlalchemy.types import Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.login import Login
    from app.models.crawl_job import CrawlJob
    from app.models.alert import Alert


class Source(Base):
    """
    Monitored external target (site / API / feed) that crawl jobs visit.

    Relationships:
        registrar  : the Login who registered this source  (many → 1)
        crawl_jobs : crawl jobs that visited this source   (1 → many)
    """
    __tablename__ = "source"

    # ── Primary key ───────────────────────────────────────────────────────
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate UUID primary key.",
    )

    # ── Identity ──────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Human-readable name for this source.",
    )
    url: Mapped[str] = mapped_column(
        Text, nullable=False, unique=True,
        comment="Canonical base URL — unique across all sources.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Optional description / notes.",
    )

    # ── Classification ────────────────────────────────────────────────────
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="web",
        comment="Category: web | api | darkweb | feed | other.",
    )

    # JSON: on PostgreSQL uses JSONB for fast querying; on SQLite stores as TEXT
    tags: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment='List of labels, e.g. ["finance", "threat-intel"].',
    )

    # ── Crawl configuration ───────────────────────────────────────────────
    crawl_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Max link-levels deep a crawl job may go (1-10).",
    )
    crawl_frequency: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual",
        comment="Scheduled cadence: manual | hourly | daily | weekly.",
    )
    allowed_paths: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment='List of URL path prefixes the crawler may follow.',
    )

    # ── Ownership ─────────────────────────────────────────────────────────
    registered_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("login.login_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="FK → login.login_id — user who registered this source.",
    )

    # ── Status ────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="False = source disabled.",
    )
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of the most recent completed crawl.",
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
    registrar: Mapped["Login"] = relationship(
        "Login",
        back_populates="registered_sources",
        foreign_keys=[registered_by],
        lazy="select",
    )
    crawl_jobs: Mapped[List["CrawlJob"]] = relationship(
        "CrawlJob",
        back_populates="source",
        foreign_keys="[CrawlJob.source_id]",
        lazy="select",
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="source",
        foreign_keys="[Alert.source_id]",
        lazy="select",
    )

    # ── Table-level constraints & indexes ─────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('web', 'api', 'darkweb', 'feed', 'other')",
            name="chk_source_type",
        ),
        CheckConstraint(
            "crawl_depth BETWEEN 1 AND 10",
            name="chk_source_crawl_depth",
        ),
        CheckConstraint(
            "crawl_frequency IN ('manual', 'hourly', 'daily', 'weekly')",
            name="chk_source_crawl_frequency",
        ),
        Index("idx_source_url",           "url"),
        Index("idx_source_source_type",   "source_type"),
        Index("idx_source_is_active",     "is_active"),
        Index("idx_source_registered_by", "registered_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<Source id={self.source_id} "
            f"name={self.name!r} type={self.source_type!r}>"
        )
