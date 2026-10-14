from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Alert, AlertState, InvalidStateTransition, Severity,
    make_fingerprint, record_alert, transition_alert,
)

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def naive(dt):
    """SQLite drops tzinfo on reload; PostgreSQL keeps it. Compare without it."""
    return dt.replace(tzinfo=None)


def new_alert(session, key="leaked db dump", **kw):
    defaults = dict(source_id=1, watchlist_id=1, key=key, severity=Severity.HIGH,
                    confidence=0.8, threat_score=70, doc_id="doc-1",
                    explain_ref="explain/1", now=T0)
    defaults.update(kw)
    return record_alert(session, **defaults)


# ---------------- normal alerts ----------------
def test_create_normal_alert(session):
    alert, created = new_alert(session)
    session.commit()
    assert created is True
    assert alert.alert_id is not None
    assert alert.state is AlertState.NEW
    assert alert.count == 1
    assert alert.first_seen == alert.last_seen
    assert alert.source.name == "Forum A"            # relationship to source
    assert alert.watchlist.name == "Bank credentials"  # relationship to watchlist
    assert len(alert.fingerprint) == 64


def test_alert_without_watchlist_is_allowed(session):
    alert, _ = new_alert(session, watchlist_id=None)
    session.commit()
    assert alert.watchlist is None


# ---------------- fingerprint / dedup ----------------
def test_fingerprint_is_stable_and_normalised():
    a = make_fingerprint(1, 1, "Leaked  DB Dump")
    b = make_fingerprint(1, 1, "leaked db dump")
    assert a == b


def test_fingerprint_differs_by_source_watchlist_and_key():
    base = make_fingerprint(1, 1, "x")
    assert base != make_fingerprint(2, 1, "x")
    assert base != make_fingerprint(1, 2, "x")
    assert base != make_fingerprint(1, None, "x")
    assert base != make_fingerprint(1, 1, "y")


def test_duplicate_fingerprint_updates_count_not_new_row(session):
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


def test_duplicate_keeps_strongest_evidence(session):
    new_alert(session, severity=Severity.MEDIUM, confidence=0.5, threat_score=40)
    alert, _ = new_alert(session, severity=Severity.CRITICAL, confidence=0.9, threat_score=95)
    assert (alert.severity, alert.confidence, alert.threat_score) == (Severity.CRITICAL, 0.9, 95)
    # a weaker repeat must not lower anything
    alert, _ = new_alert(session, severity=Severity.LOW, confidence=0.1, threat_score=5)
    assert (alert.severity, alert.confidence, alert.threat_score) == (Severity.CRITICAL, 0.9, 95)
    assert alert.count == 3


def test_same_key_different_watchlist_is_separate_alert(session):
    a, _ = new_alert(session, watchlist_id=1)
    b, created = new_alert(session, watchlist_id=2)
    assert created is True and a.alert_id != b.alert_id


def test_db_rejects_raw_duplicate_fingerprint(session):
    a, _ = new_alert(session)
    session.commit()
    dup = Alert(fingerprint=a.fingerprint, source_id=1, severity=Severity.LOW,
                confidence=0.1, threat_score=1, first_seen=T0, last_seen=T0)
    session.add(dup)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_resolved_alert_reopens_on_duplicate(session):
    alert, _ = new_alert(session)
    transition_alert(session, alert, AlertState.ACKNOWLEDGED)
    transition_alert(session, alert, AlertState.RESOLVED)
    again, created = new_alert(session, now=T0 + timedelta(days=1))
    assert created is False
    assert again.state is AlertState.NEW


def test_false_positive_stays_suppressed_on_duplicate(session):
    alert, _ = new_alert(session)
    transition_alert(session, alert, AlertState.FALSE_POSITIVE)
    again, _ = new_alert(session, now=T0 + timedelta(days=1))
    assert again.state is AlertState.FALSE_POSITIVE
    assert again.count == 2


# ---------------- state transitions ----------------
def test_valid_transition_chain(session):
    alert, _ = new_alert(session)
    transition_alert(session, alert, AlertState.ACKNOWLEDGED, assigned_to="nikhil")
    transition_alert(session, alert, AlertState.INVESTIGATING)
    transition_alert(session, alert, AlertState.ESCALATED, now=T0 + timedelta(hours=1))
    transition_alert(session, alert, AlertState.RESOLVED)
    assert alert.state is AlertState.RESOLVED
    assert alert.assigned_to == "nikhil"
    assert naive(alert.escalated_at) == naive(T0 + timedelta(hours=1))


def test_escalation_sets_escalated_at(session):
    alert, _ = new_alert(session)
    assert alert.escalated_at is None
    transition_alert(session, alert, AlertState.ESCALATED, now=T0)
    assert naive(alert.escalated_at) == naive(T0)


@pytest.mark.parametrize("start_path, bad_target", [
    ([], AlertState.RESOLVED),                                        # new -> resolved
    ([AlertState.FALSE_POSITIVE], AlertState.INVESTIGATING),          # fp -> investigating
    ([AlertState.ACKNOWLEDGED, AlertState.RESOLVED], AlertState.ESCALATED),
    ([AlertState.ESCALATED], AlertState.FALSE_POSITIVE),
])
def test_invalid_transitions_rejected(session, start_path, bad_target):
    alert, _ = new_alert(session)
    for step in start_path:
        transition_alert(session, alert, step)
    before = alert.state
    with pytest.raises(InvalidStateTransition):
        transition_alert(session, alert, bad_target)
    assert alert.state is before


# ---------------- constraints ----------------
@pytest.mark.parametrize("field, value", [
    ("threat_score", 101), ("threat_score", -1),
    ("confidence", 1.5), ("confidence", -0.1),
])
def test_range_constraints(session, field, value):
    kw = dict(severity=Severity.LOW, confidence=0.5, threat_score=10)
    kw[field] = value
    with pytest.raises(IntegrityError):
        new_alert(session, **kw)
    session.rollback()


def test_foreign_keys_enforced(session):
    with pytest.raises(IntegrityError):
        new_alert(session, source_id=999)
    session.rollback()


# ---------------- indexes ----------------
def test_expected_indexes_exist(session):
    insp = inspect(session.get_bind())
    cols = {tuple(i["column_names"]) for i in insp.get_indexes("alert")}
    for expected in [("state",), ("severity",), ("source_id",), ("watchlist_id",),
                     ("state", "severity"), ("last_seen",)]:
        assert expected in cols
    uniques = [u["column_names"] for u in insp.get_unique_constraints("alert")]
    assert ["fingerprint"] in uniques
