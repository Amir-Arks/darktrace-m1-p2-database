"""
app/models/watchlist.py
SQLAlchemy models for `watchlist` and `watchlist_version`.

Preserves the architecture and constraints defined by Nikhil:
- Immutable version history (versions are never overwritten; updates append a new version).
- Dialect-agnostic: Integer autoincrement on SQLite, BigInteger on PostgreSQL.
- Strict uniqueness and check constraints.
"""
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String, Text, DateTime, Integer, BigInteger,
    CheckConstraint, UniqueConstraint, Index, ForeignKey, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.alert import Alert


class Watchlist(Base):
    """
    Watchlist root identity table.
    Tracks name, owner, and references the active/current version.
    """
    __tablename__ = "watchlist"

    # Primary key: BIGINT on PostgreSQL, INTEGER on SQLite
    watchlist_id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"),
        primary_key=True,
        autoincrement=True,
        comment="Watchlist identifier.",
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Human-readable watchlist name.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed watchlist description.",
    )
    owner_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Owner / team responsible for this watchlist.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    current_version_id: Mapped[Optional[int]] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"),
        nullable=True,
        comment="Pointer to the active version_id in watchlist_version.",
    )

    # ── Relationships ─────────────────────────────────────────────────────
    versions: Mapped[List["WatchlistVersion"]] = relationship(
        "WatchlistVersion",
        back_populates="watchlist",
        foreign_keys="[WatchlistVersion.watchlist_id]",
        cascade="all, delete-orphan",
        order_by="desc(WatchlistVersion.version_number)",
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="watchlist",
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_watchlist_owner_name"),
    )

    def __repr__(self) -> str:
        return f"<Watchlist id={self.watchlist_id} name={self.name!r} owner={self.owner_id!r}>"


class WatchlistVersion(Base):
    """
    Immutable version history for a Watchlist.
    Every update creates a new version record, preserving past criteria for evidence.
    """
    __tablename__ = "watchlist_version"

    version_id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"),
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier for this version record.",
    )
    watchlist_id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"),
        ForeignKey("watchlist.watchlist_id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK → watchlist.watchlist_id.",
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential version number (1, 2, 3...) per watchlist.",
    )
    expression: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Matching logic / rule expression.",
    )
    scope: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Scope of the watchlist (e.g. data categories, source types).",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Severity level: low | medium | high | critical.",
    )
    created_by: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="User / analyst who authored this version.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    watchlist: Mapped["Watchlist"] = relationship(
        "Watchlist",
        back_populates="versions",
        foreign_keys=[watchlist_id],
    )

    __table_args__ = (
        UniqueConstraint("watchlist_id", "version_number", name="uq_watchlist_version_number"),
        UniqueConstraint("watchlist_id", "version_id", name="uq_watchlist_version_pair"),
        CheckConstraint("version_number > 0", name="ck_watchlist_version_number_positive"),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_watchlist_version_severity",
        ),
        Index("idx_watchlist_version_history", "watchlist_id", "version_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<WatchlistVersion id={self.version_id} watchlist_id={self.watchlist_id} "
            f"v={self.version_number} severity={self.severity!r}>"
        )
