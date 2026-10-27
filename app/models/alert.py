"""
app/models/alert.py
SQLAlchemy model for the `alert` table.

Covers:
- Standard alert fields matching DarkTrace schema.
- Foreign keys resolving to source.source_id (UUID) and watchlist.watchlist_id (BigInteger).
- SHA-256 fingerprint generation and atomic deduplication.
- Finite state machine with valid transitions and escalation timestamps.
"""
from __future__ import annotations

import enum
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, Union

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.types import Uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source import Source
    from app.models.watchlist import Watchlist


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Enums + State Machine
# --------------------------------------------------------------------------
class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertState(str, enum.Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


# Which state may move to which. Anything not listed is rejected.
ALLOWED_TRANSITIONS: dict[AlertState, set[AlertState]] = {
    AlertState.NEW: {
        AlertState.ACKNOWLEDGED,
        AlertState.INVESTIGATING,
        AlertState.ESCALATED,
        AlertState.FALSE_POSITIVE,
    },
    AlertState.ACKNOWLEDGED: {
        AlertState.INVESTIGATING,
        AlertState.ESCALATED,
        AlertState.RESOLVED,
        AlertState.FALSE_POSITIVE,
    },
    AlertState.INVESTIGATING: {
        AlertState.ESCALATED,
        AlertState.RESOLVED,
        AlertState.FALSE_POSITIVE,
    },
    AlertState.ESCALATED: {AlertState.INVESTIGATING, AlertState.RESOLVED},
    # A resolved alert can be re-opened (e.g. the same fingerprint shows up again).
    AlertState.RESOLVED: {AlertState.NEW},
    AlertState.FALSE_POSITIVE: {AlertState.NEW},
}


class InvalidStateTransition(ValueError):
    """Raised when an alert attempts an illegal lifecycle transition."""
    pass


# --------------------------------------------------------------------------
# Alert Model
# --------------------------------------------------------------------------
class Alert(Base):
    """
    Alert record surfaced by matching rules / threat classification.
    Deduplicated via unique SHA-256 fingerprint.
    """
    __tablename__ = "alert"

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dedup key: same fingerprint = same alert (see make_fingerprint)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    # FK to Source (UUID)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source.source_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # doc_id points to collected document (cross-pod reference)
    doc_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # FK to Watchlist (BIGINT on PostgreSQL, INTEGER on SQLite)
    watchlist_id: Mapped[Optional[int]] = mapped_column(
        Integer().with_variant(BigInteger, "postgresql"),
        ForeignKey("watchlist.watchlist_id", ondelete="SET NULL"),
        nullable=True,
    )

    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, native_enum=False, length=20, create_constraint=True,
             name="alert_severity", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)       # 0.0 - 1.0
    threat_score: Mapped[int] = mapped_column(Integer, nullable=False)     # 0 - 100
    explain_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    state: Mapped[AlertState] = mapped_column(
        Enum(AlertState, native_enum=False, length=20, create_constraint=True,
             name="alert_state", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AlertState.NEW,
        server_default=AlertState.NEW.value,
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # ── Relationships ─────────────────────────────────────────────────────
    source: Mapped["Source"] = relationship("Source", back_populates="alerts", lazy="joined")
    watchlist: Mapped[Optional["Watchlist"]] = relationship("Watchlist", back_populates="alerts", lazy="joined")

    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_alert_fingerprint"),
        CheckConstraint("threat_score >= 0 AND threat_score <= 100", name="ck_alert_threat_score_range"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_alert_confidence_range"),
        CheckConstraint("count >= 1", name="ck_alert_count_positive"),
        CheckConstraint("last_seen >= first_seen", name="ck_alert_seen_order"),
        Index("ix_alert_state", "state"),
        Index("ix_alert_severity", "severity"),
        Index("ix_alert_source_id", "source_id"),
        Index("ix_alert_watchlist_id", "watchlist_id"),
        # Analyst queue: "open alerts, worst first"
        Index("ix_alert_state_severity", "state", "severity"),
        Index("ix_alert_last_seen", "last_seen"),
    )

    def __repr__(self) -> str:
        return (f"<Alert id={self.alert_id} state={self.state.value} "
                f"severity={self.severity.value} count={self.count}>")


# --------------------------------------------------------------------------
# Fingerprint + Dedup + State Helpers
# --------------------------------------------------------------------------
def make_fingerprint(source_id: Union[uuid.UUID, str, int], watchlist_id: Optional[int], key: str) -> str:
    """
    SHA-256 hex digest (64 chars) over source + watchlist + content key.
    Normalised so casing and extra whitespace don't create duplicate alerts.
    """
    normalised = " ".join(key.lower().split())
    raw = f"{str(source_id)}|{watchlist_id if watchlist_id is not None else ''}|{normalised}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _bump_duplicate(alert: Alert, *, threat_score: int, confidence: float,
                    severity: Severity, now: datetime) -> None:
    alert.count += 1
    alert.last_seen = now
    # Keep the strongest evidence seen so far
    alert.threat_score = max(alert.threat_score, threat_score)
    alert.confidence = max(alert.confidence, confidence)
    severity_order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
    if severity_order.index(severity) > severity_order.index(alert.severity):
        alert.severity = severity
    # A resolved alert that fires again is re-opened
    if alert.state is AlertState.RESOLVED:
        alert.state = AlertState.NEW
        alert.escalated_at = None


def record_alert(
    session: Session,
    *,
    source_id: Union[uuid.UUID, str, int],
    key: str,
    severity: Severity,
    confidence: float,
    threat_score: int,
    watchlist_id: Optional[int] = None,
    doc_id: Optional[str] = None,
    explain_ref: Optional[str] = None,
    now: Optional[datetime] = None,
) -> tuple[Alert, bool]:
    """
    Insert a new alert, or if the fingerprint already exists, update the
    existing row (count + 1, last_seen) instead of creating a duplicate.
    Returns (alert, created).
    """
    now = now or utcnow()
    if isinstance(source_id, str):
        try:
            source_id = uuid.UUID(source_id)
        except ValueError:
            pass
    fp = make_fingerprint(source_id, watchlist_id, key)

    def _existing() -> Optional[Alert]:
        return session.execute(select(Alert).where(Alert.fingerprint == fp)).scalar_one_or_none()

    alert = _existing()
    if alert is not None:
        _bump_duplicate(alert, threat_score=threat_score, confidence=confidence,
                        severity=severity, now=now)
        session.flush()
        return alert, False

    new = Alert(
        fingerprint=fp, source_id=source_id, watchlist_id=watchlist_id, doc_id=doc_id,
        severity=severity, confidence=confidence, threat_score=threat_score,
        explain_ref=explain_ref, state=AlertState.NEW,
        first_seen=now, last_seen=now, count=1,
    )
    try:
        with session.begin_nested():       # savepoint handles concurrent duplicate insertions
            session.add(new)
            session.flush()
        return new, True
    except IntegrityError:
        alert = _existing()
        if alert is None:
            raise
        _bump_duplicate(alert, threat_score=threat_score, confidence=confidence,
                        severity=severity, now=now)
        session.flush()
        return alert, False


def transition_alert(
    session: Session,
    alert: Alert,
    new_state: AlertState,
    *,
    assigned_to: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Alert:
    """Move an alert to `new_state` if the state machine allows it."""
    if new_state not in ALLOWED_TRANSITIONS[alert.state]:
        raise InvalidStateTransition(
            f"Cannot move alert from '{alert.state.value}' to '{new_state.value}'"
        )
    now = now or utcnow()
    alert.state = new_state
    if assigned_to is not None:
        alert.assigned_to = assigned_to
    if new_state is AlertState.ESCALATED:
        alert.escalated_at = now
    session.flush()
    return alert
