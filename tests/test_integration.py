"""
tests/test_integration.py
End-to-End Integration Test Suite for DarkTrace M1 Pod 2.

Exercises the full multi-module workflow:
1. Create user/login
2. Create source
3. Create crawl job referencing source
4. Create watchlist
5. Create version 1 and version 2 for watchlist
6. Retrieve current and historical watchlist versions
7. Create alert referencing source and watchlist
8. Verify fingerprint-based deduplication and count bump
9. Verify state machine transition (NEW -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED)
10. Verify foreign key rejection across all boundary tables
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.base import Base
from app.models.login import Login
from app.models.source import Source
from app.models.crawl_job import CrawlJob
from app.models.watchlist import Watchlist, WatchlistVersion
from app.models.alert import (
    Alert, AlertState, Severity,
    record_alert, transition_alert
)


@pytest.fixture
def integrated_session():
    """In-memory SQLite database representing full migration schema with FK enforcement."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)

    with Session(engine) as s:
        yield s
    engine.dispose()


def test_full_pod2_workflow_integration(integrated_session: Session):
    """Test the complete multi-module pipeline end-to-end."""
    db = integrated_session

    # Step 1: Create authenticated user
    analyst = Login(
        login_id=uuid.uuid4(),
        username="lead_analyst",
        email="lead@darktrace.io",
        password_hash="argon2$hash_token",
        role="analyst",
    )
    db.add(analyst)
    db.flush()
    assert analyst.login_id is not None

    # Step 2: Create monitored Source (Anil)
    source = Source(
        source_id=uuid.uuid4(),
        name="Dread Forum - Darknet",
        url="http://dreadmarket.onion",
        source_type="darkweb",
        registered_by=analyst.login_id,
        crawl_depth=3,
        crawl_frequency="daily",
    )
    db.add(source)
    db.flush()
    assert source.source_id is not None
    assert source.registrar.username == "lead_analyst"

    # Step 3: Create CrawlJob linked to Source (Anil)
    crawl_job = CrawlJob(
        job_id=uuid.uuid4(),
        triggered_by=analyst.login_id,
        source_id=source.source_id,
        job_name="Scheduled Crawl #101",
        status="running",
        depth_used=2,
        started_at=datetime.now(timezone.utc),
    )
    db.add(crawl_job)
    db.flush()
    assert crawl_job.source.name == "Dread Forum - Darknet"
    assert crawl_job.triggerer.username == "lead_analyst"

    # Step 4 & 5: Create Watchlist with Version 1 and Version 2 (Nikhil)
    watchlist = Watchlist(
        name="Defense Contractor Leak Watch",
        description="Detects leaks relating to aerospace and defense assets",
        owner_id="intel_defense_unit",
    )
    db.add(watchlist)
    db.flush()

    v1 = WatchlistVersion(
        watchlist_id=watchlist.watchlist_id,
        version_number=1,
        expression="text contains 'top_secret_schematic'",
        scope="darkweb_forums",
        severity="medium",
        created_by="nikhil.kalokhe",
    )
    db.add(v1)
    db.flush()
    watchlist.current_version_id = v1.version_id

    # Append Version 2
    v2 = WatchlistVersion(
        watchlist_id=watchlist.watchlist_id,
        version_number=2,
        expression="text contains 'top_secret_schematic' OR cve in ('CVE-2026-9999')",
        scope="darkweb_forums, paste_bins",
        severity="critical",
        created_by="nikhil.kalokhe",
    )
    db.add(v2)
    db.flush()
    watchlist.current_version_id = v2.version_id
    db.commit()

    # Step 6: Verify historical preservation
    all_versions = db.execute(
        select(WatchlistVersion)
        .where(WatchlistVersion.watchlist_id == watchlist.watchlist_id)
        .order_by(WatchlistVersion.version_number.asc())
    ).scalars().all()
    assert len(all_versions) == 2
    assert all_versions[0].version_number == 1
    assert all_versions[1].version_number == 2
    assert watchlist.current_version_id == v2.version_id

    # Step 7: Create Alert linked to Source and Watchlist
    alert, created = record_alert(
        db,
        source_id=source.source_id,
        watchlist_id=watchlist.watchlist_id,
        key="aerospace_cad_leak_thread_4512",
        severity=Severity.CRITICAL,
        confidence=0.92,
        threat_score=88,
        doc_id="doc_onion_88412",
        explain_ref="nlp/scoring/exp_01",
    )
    db.commit()
    assert created is True
    assert alert.alert_id is not None
    assert alert.source.source_id == source.source_id
    assert alert.watchlist.name == "Defense Contractor Leak Watch"
    assert alert.count == 1

    # Step 8: Verify Deduplication on duplicate hit
    alert_repeat, repeat_created = record_alert(
        db,
        source_id=source.source_id,
        watchlist_id=watchlist.watchlist_id,
        key="aerospace_cad_leak_thread_4512",
        severity=Severity.CRITICAL,
        confidence=0.95,
        threat_score=92,
    )
    db.commit()
    assert repeat_created is False
    assert alert_repeat.alert_id == alert.alert_id
    assert alert_repeat.count == 2
    assert alert_repeat.threat_score == 92  # Kept strongest evidence

    # Step 9: State Machine Lifecycle
    transition_alert(db, alert_repeat, AlertState.ACKNOWLEDGED, assigned_to="amir_ashraf")
    transition_alert(db, alert_repeat, AlertState.INVESTIGATING)
    transition_alert(db, alert_repeat, AlertState.RESOLVED)
    db.commit()
    assert alert_repeat.state is AlertState.RESOLVED

    # Step 10: Reject invalid cross-boundary foreign keys
    with pytest.raises(IntegrityError):
        # Invalid source_id for crawl_job
        bad_job = CrawlJob(
            job_id=uuid.uuid4(),
            triggered_by=analyst.login_id,
            source_id=uuid.uuid4(),  # Nonexistent
        )
        db.add(bad_job)
        db.flush()
    db.rollback()

    with pytest.raises(IntegrityError):
        # Invalid source_id for alert
        record_alert(
            db,
            source_id=uuid.uuid4(),  # Nonexistent
            key="random_key",
            severity=Severity.LOW,
            confidence=0.5,
            threat_score=10,
        )
    db.rollback()
