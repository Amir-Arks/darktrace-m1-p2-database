"""
app/models/crawl_job.py
SQLAlchemy model for the `crawl_job` table.
Dialect-agnostic — works on SQLite (dev) AND PostgreSQL (prod).

Central link:
    login (triggered_by) → crawl_job → source (source_id)
    WHO triggered the crawl?  WHAT job?  WHICH site was visited?
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

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
    from app.models.source import Source


class CrawlJob(Base):
    """
    A crawl attempt — links WHO triggered it (Login) to WHICH site (Source).

    Status lifecycle:
        pending → running → completed
                          └→ failed
                          └→ cancelled
    """
    __tablename__ = "crawl_job"

    # ── Primary key ───────────────────────────────────────────────────────
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate UUID primary key.",
    )

    # ── WHO triggered this crawl ──────────────────────────────────────────
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("login.login_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="FK → login.login_id — user who triggered this crawl.",
    )

    # ── WHICH site is being crawled ───────────────────────────────────────
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source.source_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="FK → source.source_id — target site being crawled.",
    )

    # ── Job identity ──────────────────────────────────────────────────────
    job_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
        comment="Optional human-readable label for this job.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Optional notes about this crawl job.",
    )

    # ── Configuration snapshot (captures settings at job creation time) ───
    depth_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Crawl depth used for this specific job (1-10).",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
        comment="HTTP User-Agent string used during this crawl.",
    )
    # JSON: JSONB on PostgreSQL, TEXT on SQLite
    extra_config: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment="Flexible per-job crawler settings (JSON).",
    )

    # ── Lifecycle / status ────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="Job state: pending | running | completed | failed | cancelled.",
    )

    # ── Timing ────────────────────────────────────────────────────────────
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When scheduled; NULL = triggered immediately.",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the crawler actually started running.",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the crawler finished (success, failure, or cancel).",
    )

    # ── Results / metrics ─────────────────────────────────────────────────
    pages_crawled: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Count of pages successfully crawled.",
    )
    errors_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Count of errors encountered during crawl.",
    )
    error_details: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Summary of the last / most critical error.",
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
    triggerer: Mapped["Login"] = relationship(
        "Login",
        back_populates="crawl_jobs",
        foreign_keys=[triggered_by],
        lazy="select",
    )
    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="crawl_jobs",
        foreign_keys=[source_id],
        lazy="select",
    )

    # ── Table-level constraints & indexes ─────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="chk_crawl_job_status",
        ),
        CheckConstraint(
            "depth_used BETWEEN 1 AND 10",
            name="chk_crawl_job_depth",
        ),
        CheckConstraint(
            "pages_crawled >= 0",
            name="chk_crawl_job_pages_crawled",
        ),
        CheckConstraint(
            "errors_count >= 0",
            name="chk_crawl_job_errors_count",
        ),
        CheckConstraint(
            # SQLite & PostgreSQL both support this syntax
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="chk_crawl_job_timing",
        ),
        Index("idx_crawl_job_triggered_by", "triggered_by"),
        Index("idx_crawl_job_source_id",    "source_id"),
        Index("idx_crawl_job_status",       "status"),
        Index("idx_crawl_job_created_at",   "created_at"),
        Index("idx_crawl_job_scheduled_at", "scheduled_at"),
        # Composite: find all jobs for a user+source pair fast
        Index("idx_crawl_job_user_source",  "triggered_by", "source_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CrawlJob id={self.job_id} status={self.status!r} "
            f"triggered_by={self.triggered_by} source_id={self.source_id}>"
        )
