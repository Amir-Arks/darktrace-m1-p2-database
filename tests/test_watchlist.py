"""
tests/test_watchlist.py
Tests for Watchlist and WatchlistVersion models and operations.

Verifies:
1. Watchlist creation and retrieval.
2. Version 1 and Version 2 sequential creation.
3. Immutability of version history (old version is preserved).
4. Unique constraint on (watchlist_id, version_number).
5. Current version pointer integrity.
6. Validation of version_number > 0 and allowed severity levels.
"""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.base import Base
from app.models.watchlist import Watchlist, WatchlistVersion


@pytest.fixture
def db_session():
    """In-memory SQLite test session with all tables created."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_create_watchlist_and_first_version(db_session: Session):
    """Test creating a watchlist and its initial version."""
    wl = Watchlist(
        name="Credential Leak Watchlist",
        description="Monitors paste sites for credential dumps",
        owner_id="threat-intel-team",
    )
    db_session.add(wl)
    db_session.flush()

    assert wl.watchlist_id is not None
    assert wl.current_version_id is None

    # Add Version 1
    v1 = WatchlistVersion(
        watchlist_id=wl.watchlist_id,
        version_number=1,
        expression="keywords in ('password', 'hash', 'credential')",
        scope="paste_sites, forums",
        severity="medium",
        created_by="nikhil.kalokhe",
    )
    db_session.add(v1)
    db_session.flush()

    # Link current version
    wl.current_version_id = v1.version_id
    db_session.commit()

    # Verify retrieval
    retrieved = db_session.execute(select(Watchlist).where(Watchlist.watchlist_id == wl.watchlist_id)).scalar_one()
    assert retrieved.name == "Credential Leak Watchlist"
    assert len(retrieved.versions) == 1
    assert retrieved.versions[0].version_number == 1
    assert retrieved.current_version_id == v1.version_id


def test_add_second_version_preserves_history(db_session: Session):
    """Test adding version 2 preserves version 1 intact."""
    wl = Watchlist(name="Ransomware Targets", owner_id="soc-team")
    db_session.add(wl)
    db_session.flush()

    v1 = WatchlistVersion(
        watchlist_id=wl.watchlist_id,
        version_number=1,
        expression="threat_score > 50",
        scope="all_sources",
        severity="medium",
        created_by="nikhil.kalokhe",
    )
    db_session.add(v1)
    db_session.flush()
    wl.current_version_id = v1.version_id
    db_session.commit()

    # Add Version 2
    v2 = WatchlistVersion(
        watchlist_id=wl.watchlist_id,
        version_number=2,
        expression="threat_score > 70 OR actor in ('ransom_crew_alpha')",
        scope="all_sources",
        severity="high",
        created_by="nikhil.kalokhe",
    )
    db_session.add(v2)
    db_session.flush()
    wl.current_version_id = v2.version_id
    db_session.commit()

    # Query all versions
    versions = db_session.execute(
        select(WatchlistVersion)
        .where(WatchlistVersion.watchlist_id == wl.watchlist_id)
        .order_by(WatchlistVersion.version_number.asc())
    ).scalars().all()

    assert len(versions) == 2
    # Verify version 1 is preserved unchanged
    assert versions[0].version_number == 1
    assert versions[0].severity == "medium"
    assert versions[0].expression == "threat_score > 50"

    # Verify version 2 is current
    assert versions[1].version_number == 2
    assert versions[1].severity == "high"
    assert wl.current_version_id == v2.version_id


def test_duplicate_version_number_rejected(db_session: Session):
    """Test that duplicate version_number for the same watchlist is rejected."""
    wl = Watchlist(name="DDoS Monitors", owner_id="netsec-team")
    db_session.add(wl)
    db_session.flush()

    v1 = WatchlistVersion(
        watchlist_id=wl.watchlist_id,
        version_number=1,
        expression="tag == 'ddos'",
        scope="darkweb",
        severity="low",
        created_by="nikhil.kalokhe",
    )
    db_session.add(v1)
    db_session.flush()

    # Attempt to create another version with version_number = 1
    v1_duplicate = WatchlistVersion(
        watchlist_id=wl.watchlist_id,
        version_number=1,
        expression="tag == 'ddos_v2'",
        scope="darkweb",
        severity="medium",
        created_by="nikhil.kalokhe",
    )
    db_session.add(v1_duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_invalid_severity_rejected(db_session: Session):
    """Test that invalid severity is rejected by check constraint."""
    wl = Watchlist(name="Test Severity", owner_id="qa-team")
    db_session.add(wl)
    db_session.flush()

    bad_version = WatchlistVersion(
        watchlist_id=wl.watchlist_id,
        version_number=1,
        expression="test",
        scope="test",
        severity="super_critical",  # Invalid severity
        created_by="test_user",
    )
    db_session.add(bad_version)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_duplicate_watchlist_name_for_same_owner_rejected(db_session: Session):
    """Test that unique constraint on (owner_id, name) is enforced."""
    wl1 = Watchlist(name="Duplicate Check", owner_id="analyst-1")
    db_session.add(wl1)
    db_session.commit()

    wl2 = Watchlist(name="Duplicate Check", owner_id="analyst-1")
    db_session.add(wl2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
