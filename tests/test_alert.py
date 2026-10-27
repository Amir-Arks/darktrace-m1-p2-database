"""
tests/test_alert.py
Comprehensive test suite for Alert model, deduplication, and finite state transitions.

Test suite for Alert model, deduplication, and finite state transitions.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.base import Base
from app.models.login import Login
from app.models.source import Source
from app.models.watchlist import Watchlist
from app.models.alert import (
    Alert, AlertState, InvalidStateTransition, Severity,
    make_fingerprint, record_alert, transition_alert,
)

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def naive(dt):
    """SQLite drops tzinfo on reload; compare timestamps without tzinfo."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None)


@pytest.fixture
def session():
    """In-memory SQLite test session with registered Login, Source, and Watchlists."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    with Session(engine) as s:
        # Create a test Login
        user = Login(
            login_id=uuid.uuid4(),
            username="analyst_sec",
            email="analyst@darktrace.local",
            password_hash="argon2$fakehash",
            role="analyst",
        )
        s.add(user)
        s.flush()

        # Create test Sources
        src1 = Source(
            source_id=uuid.uuid4(),
            name="Forum A",
            url="http://darkforum.onion",
            source_type="darkweb",
            registered_by=user.login_id,
        )
        src2 = Source(
            source_id=uuid.uuid4(),
            name="Marketplace B",
            url="http://market.onion",
            source_type="darkweb",
            registered_by=user.login_id,
        )
        s.add_all([src1, src2])

        # Create test Watchlists
        wl1 = Watchlist(watchlist_id=1, name="Bank credentials", owner_id="sec-team")
        wl2 = Watchlist(watchlist_id=2, name="Malware sales", owner_id="sec-team")
        s.add_all([wl1, wl2])

        s.commit()
        yield s
    engine.dispose()


def get_first_source_id(session: Session) -> uuid.UUID:
    return session.execute(select(Source.source_id).where(Source.name == "Forum A")).scalar_one()


def new_alert(session: Session, key="leaked db dump", **kw):
    src_id = kw.pop("source_id", None) or get_first_source_id(session)
    defaults = dict(
        source_id=src_id,
        watchlist_id=1,
        key=key,
        severity=Severity.HIGH,
        confidence=0.8,
        threat_score=70,
        doc_id="doc-1",
        explain_ref="explain/1",
        now=T0,
    )
    defaults.update(kw)
    return record_alert(session, **defaults)


# ---------------- Normal Alerts ----------------
def test_create_normal_alert(session: Session):
    alert, created = new_alert(session)
    session.commit()
    assert created is True
    assert alert.alert_id is not None
    assert alert.state is AlertState.NEW
    assert alert.count == 1
    assert alert.first_seen == alert.last_seen
    assert alert.source.name == "Forum A"
    assert alert.watchlist.name == "Bank credentials"
    assert len(alert.fingerprint) == 64


def test_alert_without_watchlist_is_allowed(session: Session):
    alert, _ = new_alert(session, watchlist_id=None)
    session.commit()
    assert alert.watchlist is None


# ---------------- Fingerprint / Dedup ----------------
def test_fingerprint_is_stable_and_normalised():
    src_id = uuid.uuid4()
    a = make_fingerprint(src_id, 1, "Leaked  DB Dump")
    b = make_fingerprint(src_id, 1, "leaked db dump")
    assert a == b


def test_fingerprint_differs_by_source_watchlist_and_key():
    src1, src2 = uuid.uuid4(), uuid.uuid4()
    base = make_fingerprint(src1, 1, "x")
    assert base != make_fingerprint(src2, 1, "x")
    assert base != make_fingerprint(src1, 2, "x")
    assert base != make_fingerprint(src1, None, "x")
    assert base != make_fingerprint(src1, 1, "y")


def test_duplicate_fingerprint_updates_count_not_new_row(session: Session):
    first, c1 = new_alert(session)
    later = T0 + timedelta(hours=2)
    second, c2 = new_alert(session, now=later, key="LEAKED DB DUMP")
    session.commit()
    assert (c1, c2) == (True, False)
    assert first.alert_id == second.alert_id
    assert len(session.scalars(select(Alert)).all()) == 1
    assert second.count == 2
    assert naive(second.first_seen) == naive(T0)
    assert naive(second.last_seen) == naive(later)


def test_duplicate_keeps_strongest_evidence(session: Session):
    new_alert(session, severity=Severity.MEDIUM, confidence=0.5, threat_score=40)
    alert, _ = new_alert(session, severity=Severity.CRITICAL, confidence=0.9, threat_score=95)
    assert (alert.severity, alert.confidence, alert.threat_score) == (Severity.CRITICAL, 0.9, 95)
    # A weaker repeat must not lower anything
    alert, _ = new_alert(session, severity=Severity.LOW, confidence=0.1, threat_score=5)
    assert (alert.severity, alert.confidence, alert.threat_score) == (Severity.CRITICAL, 0.9, 95)
    assert alert.count == 3


def test_same_key_different_watchlist_is_separate_alert(session: Session):
    a, _ = new_alert(session, watchlist_id=1)
    b, created = new_alert(session, watchlist_id=2)
    assert created is True and a.alert_id != b.alert_id


def test_db_rejects_raw_duplicate_fingerprint(session: Session):
    a, _ = new_alert(session)
    session.commit()
    dup = Alert(
        fingerprint=a.fingerprint,
        source_id=a.source_id,
        severity=Severity.LOW,
        confidence=0.1,
        threat_score=1,
        first_seen=T0,
        last_seen=T0,
    )
    session.add(dup)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_resolved_alert_reopens_on_duplicate(session: Session):
    alert, _ = new_alert(session)
    transition_alert(session, alert, AlertState.ACKNOWLEDGED)
    transition_alert(session, alert, AlertState.RESOLVED)
    again, created = new_alert(session, now=T0 + timedelta(days=1))
    assert created is False
    assert again.state is AlertState.NEW


def test_false_positive_stays_suppressed_on_duplicate(session: Session):
    alert, _ = new_alert(session)
    transition_alert(session, alert, AlertState.FALSE_POSITIVE)
    again, _ = new_alert(session, now=T0 + timedelta(days=1))
    assert again.state is AlertState.FALSE_POSITIVE
    assert again.count == 2


# ---------------- State Transitions ----------------
def test_valid_transition_chain(session: Session):
    alert, _ = new_alert(session)
    transition_alert(session, alert, AlertState.ACKNOWLEDGED, assigned_to="amir")
    transition_alert(session, alert, AlertState.INVESTIGATING)
    transition_alert(session, alert, AlertState.ESCALATED, now=T0 + timedelta(hours=1))
    transition_alert(session, alert, AlertState.RESOLVED)
    assert alert.state is AlertState.RESOLVED
    assert alert.assigned_to == "amir"
    assert naive(alert.escalated_at) == naive(T0 + timedelta(hours=1))


def test_escalation_sets_escalated_at(session: Session):
    alert, _ = new_alert(session)
    assert alert.escalated_at is None
    transition_alert(session, alert, AlertState.ESCALATED, now=T0)
    assert naive(alert.escalated_at) == naive(T0)


@pytest.mark.parametrize("start_path, bad_target", [
    ([], AlertState.RESOLVED),
    ([AlertState.FALSE_POSITIVE], AlertState.INVESTIGATING),
    ([AlertState.ACKNOWLEDGED, AlertState.RESOLVED], AlertState.ESCALATED),
    ([AlertState.ESCALATED], AlertState.FALSE_POSITIVE),
])
def test_invalid_transitions_rejected(session: Session, start_path, bad_target):
    alert, _ = new_alert(session)
    for step in start_path:
        transition_alert(session, alert, step)
    before = alert.state
    with pytest.raises(InvalidStateTransition):
        transition_alert(session, alert, bad_target)
    assert alert.state is before


# ---------------- Constraints ----------------
@pytest.mark.parametrize("field, value", [
    ("threat_score", 101), ("threat_score", -1),
    ("confidence", 1.5), ("confidence", -0.1),
])
def test_range_constraints(session: Session, field, value):
    kw = dict(severity=Severity.LOW, confidence=0.5, threat_score=10)
    kw[field] = value
    with pytest.raises(IntegrityError):
        new_alert(session, **kw)
    session.rollback()


def test_foreign_keys_enforced(session: Session):
    fake_source_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        new_alert(session, source_id=fake_source_id)
    session.rollback()


# ---------------- Indexes ----------------
def test_expected_indexes_exist(session: Session):
    insp = inspect(session.get_bind())
    cols = {tuple(i["column_names"]) for i in insp.get_indexes("alert")}
    for expected in [("state",), ("severity",), ("source_id",), ("watchlist_id",),
                     ("state", "severity"), ("last_seen",)]:
        assert expected in cols
    uniques = [u["column_names"] for u in insp.get_unique_constraints("alert")]
    assert ["fingerprint"] in uniques
