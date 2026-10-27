"""
tests/test_source_crawl.py
Member 2 — Anil Kumar
DarkTrace Pod 2: Source + Crawl Job test suite (Spec D — all 8 cases).

Tests run against an isolated in-memory SQLite database with FK enforcement ON.
"""
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.models.base import Base
from app.models.login import Login
from app.models.source import Source
from app.models.crawl_job import CrawlJob
from app.schemas.source import SourceCreate, SourceUpdate
from app.schemas.crawl_job import CrawlJobCreate, CrawlJobStatusUpdate
from app.services.source_service import SourceService
from app.services.crawl_job_service import CrawlJobService


# ──────────────────────────────────────────────
# Test database setup (in-memory SQLite per test)
# ──────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_session() -> Session:
    """Provide a clean SQLite in-memory session for each test with FK enforcement."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def make_login(db: Session) -> Login:
    user = Login(
        username="anil_test",
        email="anil@darktrace.dev",
        password_hash="hashed_pw_placeholder",
        role="analyst",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_source(db: Session, user: Login, url: str = "https://example.com") -> Source:
    return SourceService.create_source(db, SourceCreate(
        name="Example Site",
        url=url,
        source_type="web",
        crawl_depth=2,
        crawl_frequency="daily",
        registered_by=user.login_id,
    ))


# ══════════════════════════════════════════════
# TEST CASES
# ══════════════════════════════════════════════

class TestSourceOperations:
    """Spec D-1 and D-2: Create and read a valid source."""

    def test_create_valid_source(self, db_session):
        """D-1: Create a valid source and verify it is persisted correctly."""
        user = make_login(db_session)

        source = SourceService.create_source(db_session, SourceCreate(
            name="DarkWeb Monitor",
            url="https://monitor.dark.example",
            source_type="darkweb",
            crawl_depth=3,
            crawl_frequency="weekly",
            tags=["threat-intel", "darkweb"],
            registered_by=user.login_id,
            is_active=True,
        ))

        assert source.source_id is not None
        assert source.name == "DarkWeb Monitor"
        assert source.url == "https://monitor.dark.example"
        assert source.source_type == "darkweb"
        assert source.crawl_depth == 3
        assert source.crawl_frequency == "weekly"
        assert source.is_active is True
        assert source.registered_by == user.login_id
        assert source.created_at is not None

    def test_read_source(self, db_session):
        """D-2: Read a source back from DB by its UUID."""
        user = make_login(db_session)
        created = make_source(db_session, user)

        fetched = SourceService.get_source(db_session, created.source_id)

        assert fetched is not None
        assert fetched.source_id == created.source_id
        assert fetched.url == "https://example.com"
        assert fetched.name == "Example Site"

    def test_read_nonexistent_source_returns_none(self, db_session):
        """Reading a non-existent source UUID returns None."""
        result = SourceService.get_source(db_session, uuid.uuid4())
        assert result is None

    def test_create_source_with_invalid_user_raises(self, db_session):
        """Source creation with non-existent registered_by UUID raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            SourceService.create_source(db_session, SourceCreate(
                name="Ghost Source",
                url="https://ghost.example",
                source_type="web",
                crawl_depth=1,
                crawl_frequency="manual",
                registered_by=uuid.uuid4(),
            ))

    def test_duplicate_url_rejected(self, db_session):
        """Creating two sources with the same URL raises ValueError."""
        user = make_login(db_session)
        make_source(db_session, user, url="https://duplicate.com")

        with pytest.raises(ValueError, match="already exists"):
            make_source(db_session, user, url="https://duplicate.com")


class TestCrawlJobOperations:
    """Spec D-3 and D-4: Create and read a crawl job."""

    def test_create_crawl_job_for_source(self, db_session):
        """D-3: Create a crawl job referencing a valid source."""
        user = make_login(db_session)
        source = make_source(db_session, user)

        job = CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
            triggered_by=user.login_id,
            source_id=source.source_id,
            depth_used=2,
        ))

        assert job.job_id is not None
        assert job.source_id == source.source_id
        assert job.triggered_by == user.login_id
        assert job.status == "pending"
        assert job.pages_crawled == 0
        assert job.errors_count == 0
        assert job.created_at is not None

    def test_read_crawl_job(self, db_session):
        """D-4: Read a crawl job back from DB by its UUID."""
        user = make_login(db_session)
        source = make_source(db_session, user)

        created_job = CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
            triggered_by=user.login_id,
            source_id=source.source_id,
            depth_used=1,
        ))

        fetched_job = CrawlJobService.get_crawl_job(db_session, created_job.job_id)

        assert fetched_job is not None
        assert fetched_job.job_id == created_job.job_id
        assert fetched_job.source_id == source.source_id
        assert fetched_job.status == "pending"


class TestJobStateTransitions:
    """Spec D-5, D-6, D-7: Job status lifecycle (success, failure, repeated)."""

    def test_successful_job_state(self, db_session):
        """D-5: Transition a job from pending -> running -> completed."""
        user = make_login(db_session)
        source = make_source(db_session, user)

        job = CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
            triggered_by=user.login_id,
            source_id=source.source_id,
            depth_used=1,
        ))
        assert job.status == "pending"

        job = CrawlJobService.update_job_status(db_session, job.job_id, CrawlJobStatusUpdate(
            status="running",
        ))
        assert job.status == "running"
        assert job.started_at is not None

        job = CrawlJobService.update_job_status(db_session, job.job_id, CrawlJobStatusUpdate(
            status="completed",
            pages_crawled=45,
            errors_count=0,
        ))
        assert job.status == "completed"
        assert job.pages_crawled == 45
        assert job.errors_count == 0
        assert job.completed_at is not None

        # Source last_crawled_at should be updated on successful completion
        db_session.refresh(source)
        assert source.last_crawled_at is not None

    def test_failed_job_state(self, db_session):
        """D-6: Transition a job from pending -> running -> failed with error details."""
        user = make_login(db_session)
        source = make_source(db_session, user)

        job = CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
            triggered_by=user.login_id,
            source_id=source.source_id,
            depth_used=1,
        ))

        job = CrawlJobService.update_job_status(db_session, job.job_id, CrawlJobStatusUpdate(
            status="running",
        ))
        assert job.status == "running"

        job = CrawlJobService.update_job_status(db_session, job.job_id, CrawlJobStatusUpdate(
            status="failed",
            pages_crawled=3,
            errors_count=5,
            error_details="Connection timeout: site unreachable after 5 retries.",
        ))

        assert job.status == "failed"
        assert job.errors_count == 5
        assert job.error_details == "Connection timeout: site unreachable after 5 retries."
        assert job.completed_at is not None

    def test_repeated_jobs_for_same_source(self, db_session):
        """D-7: Multiple crawl jobs can be created for the same source (repeated/attempted)."""
        user = make_login(db_session)
        source = make_source(db_session, user)

        job1 = CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
            triggered_by=user.login_id, source_id=source.source_id, depth_used=1,
        ))
        job2 = CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
            triggered_by=user.login_id, source_id=source.source_id, depth_used=2,
            job_name="Retry Crawl 1",
        ))
        job3 = CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
            triggered_by=user.login_id, source_id=source.source_id, depth_used=1,
            job_name="Retry Crawl 2",
        ))

        assert job1.job_id != job2.job_id
        assert job2.job_id != job3.job_id
        assert job1.source_id == job2.source_id == job3.source_id == source.source_id

        jobs = CrawlJobService.list_crawl_jobs_for_source(db_session, source.source_id)
        assert len(jobs) == 3

        CrawlJobService.update_job_status(db_session, job1.job_id, CrawlJobStatusUpdate(status="completed", pages_crawled=10))
        CrawlJobService.update_job_status(db_session, job2.job_id, CrawlJobStatusUpdate(status="failed", error_details="Timeout"))
        CrawlJobService.update_job_status(db_session, job3.job_id, CrawlJobStatusUpdate(status="cancelled"))

        assert CrawlJobService.get_crawl_job(db_session, job1.job_id).status == "completed"
        assert CrawlJobService.get_crawl_job(db_session, job2.job_id).status == "failed"
        assert CrawlJobService.get_crawl_job(db_session, job3.job_id).status == "cancelled"


class TestForeignKeyEnforcement:
    """Spec D-8: Creating a job with an invalid source ID must be rejected."""

    def test_invalid_source_id_rejected(self, db_session):
        """D-8: CrawlJob creation with a non-existent source_id raises ValueError."""
        user = make_login(db_session)
        fake_source_id = uuid.uuid4()

        with pytest.raises(ValueError, match="does not exist"):
            CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
                triggered_by=user.login_id,
                source_id=fake_source_id,
                depth_used=1,
            ))

    def test_invalid_user_for_job_rejected(self, db_session):
        """CrawlJob creation with a non-existent triggered_by UUID raises ValueError."""
        user = make_login(db_session)
        source = make_source(db_session, user)
        fake_user_id = uuid.uuid4()

        with pytest.raises(ValueError, match="does not exist"):
            CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
                triggered_by=fake_user_id,
                source_id=source.source_id,
                depth_used=1,
            ))

    def test_error_message_identifies_invalid_source(self, db_session):
        """Verify the error message clearly names the invalid source ID."""
        user = make_login(db_session)
        bad_id = uuid.uuid4()

        try:
            CrawlJobService.create_crawl_job(db_session, CrawlJobCreate(
                triggered_by=user.login_id,
                source_id=bad_id,
                depth_used=1,
            ))
            assert False, "Expected ValueError was not raised"
        except ValueError as e:
            assert str(bad_id) in str(e)
            assert "does not exist" in str(e)
