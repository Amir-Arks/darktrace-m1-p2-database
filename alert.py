"""
Alert table model.

Covers: fields from the project schema, FK relationships to source and
watchlist, fingerprint-based de-duplication, state machine, and indexes.
"""
from __future__ import annotations

import enum
import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Enums
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
        AlertState.ACKNOWLEDGED, AlertState.INVESTIGATING,
        AlertState.ESCALATED, AlertState.FALSE_POSITIVE,
    },
    AlertState.ACKNOWLEDGED: {
        AlertState.INVESTIGATING, AlertState.ESCALATED,
        AlertState.RESOLVED, AlertState.FALSE_POSITIVE,
    },
    AlertState.INVESTIGATING: {
        AlertState.ESCALATED, AlertState.RESOLVED, AlertState.FALSE_POSITIVE,
    },
    AlertState.ESCALATED: {AlertState.INVESTIGATING, AlertState.RESOLVED},
    # A resolved alert can be re-opened (e.g. the same fingerprint shows up again).
    AlertState.RESOLVED: {AlertState.NEW},
    AlertState.FALSE_POSITIVE: {AlertState.NEW},
}


class InvalidStateTransition(ValueError):
    pass


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alert"

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dedup key: same fingerprint = same alert (see make_fingerprint)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.source_id", ondelete="RESTRICT"), nullable=False
    )
    # doc_id points to the collected document. Kept as a plain column because
    # the document table belongs to another pod; add a FK once it exists.
    doc_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    watchlist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("watchlist.watchlist_id", ondelete="SET NULL"), nullable=True
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

    source = relationship("Source", lazy="joined")
    watchlist = relationship("Watchlist", lazy="joined")

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
# Fingerprint + dedup + state helpers
# --------------------------------------------------------------------------
def make_fingerprint(source_id: int, watchlist_id: Optional[int], key: str) -> str:
    """
    SHA-256 hex digest (64 chars) over source + watchlist + a content key.
    `key` should identify the finding itself, e.g. the matched keyword plus a
    normalised post/listing id or content hash. Normalised so that casing and
    extra spaces don't create "different" alerts.
    """
    normalised = " ".join(key.lower().split())
    raw = f"{source_id}|{watchlist_id if watchlist_id is not None else ''}|{normalised}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _bump_duplicate(alert: Alert, *, threat_score: int, confidence: float,
                    severity: Severity, now: datetime) -> None:
    alert.count += 1
    alert.last_seen = now
    # Keep the strongest evidence seen so far.
    alert.threat_score = max(alert.threat_score, threat_score)
    alert.confidence = max(alert.confidence, confidence)
    if list(Severity).index(severity) > list(Severity).index(alert.severity):
        alert.severity = severity
    # A resolved alert that fires again is re-opened.
    if alert.state is AlertState.RESOLVED:
        alert.state = AlertState.NEW
        alert.escalated_at = None


def record_alert(
    session: Session,
    *,
    source_id: int,
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
        with session.begin_nested():       # savepoint, so a race doesn't kill the session
            session.add(new)
            session.flush()
        return new, True
    except IntegrityError:
        # Another worker inserted the same fingerprint first -> treat as duplicate.
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
