"""
tests/test_fk_enforcement.py
Proves that SQLite foreign key enforcement is active and correctly
rejects invalid triggered_by and source_id values in crawl_job.
"""
import uuid
import pytest

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.models import Base
from app.models.login import Login
from app.models.source import Source
from app.models.crawl_job import CrawlJob
from app.database import _apply_sqlite_pragmas


# ── In-memory SQLite engine for isolated tests ────────────────────────────────
TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)

# Apply FK pragma on connect AND checkout (same two-layer approach as production)
@event.listens_for(engine, "connect")
def on_connect(dbapi_conn, _):
    _apply_sqlite_pragmas(dbapi_conn)

@event.listens_for(engine, "checkout")
def on_checkout(dbapi_conn, _, __):
    _apply_sqlite_pragmas(dbapi_conn)

TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Create all tables once for the module."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Provide a clean session per test, always rolled back."""
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ── Helper: create a valid login ──────────────────────────────────────────────
def make_login(db, username="testuser"):
    user = Login(
        username=username,
        email=f"{username}@test.com",
        password_hash="hashed_pw",
        role="analyst",
    )
    db.add(user)
    db.flush()  # assign login_id without committing
    return user


# ── Helper: create a valid source ─────────────────────────────────────────────
def make_source(db, registered_by, url="https://example.com"):
    src = Source(
        name="Test Source",
        url=url,
        source_type="web",
        registered_by=registered_by,
    )
    db.add(src)
    db.flush()
    return src


# ═════════════════════════════════════════════════════════════════════════════
# TEST 1 — Verify PRAGMA foreign_keys is ON
# ═════════════════════════════════════════════════════════════════════════════
def test_pragma_foreign_keys_is_on(db):
    """PRAGMA foreign_keys must return 1 (ON) on every connection."""
    result = db.execute(text("PRAGMA foreign_keys")).fetchone()
    assert result is not None, "PRAGMA query returned no rows"
    assert result[0] == 1, (
        f"SQLite FK enforcement is OFF (PRAGMA foreign_keys = {result[0]}). "
        "The 'connect'/'checkout' event hooks are not working correctly."
    )


# ═════════════════════════════════════════════════════════════════════════════
# TEST 2 — Valid crawl_job creation (happy path)
# ═════════════════════════════════════════════════════════════════════════════
def test_valid_crawl_job_creation(db):
    """A crawl_job with valid triggered_by and source_id must be saved."""
    user = make_login(db, "valid_user")
    src  = make_source(db, registered_by=user.login_id, url="https://valid.com")

    job = CrawlJob(
        triggered_by=user.login_id,
        source_id=src.source_id,
        status="pending",
    )
    db.add(job)
    db.flush()  # should succeed with no exception

    assert job.job_id is not None
    assert job.status == "pending"


# ═════════════════════════════════════════════════════════════════════════════
# TEST 3 — FK violation: triggered_by references non-existent login
# ═════════════════════════════════════════════════════════════════════════════
def test_crawl_job_rejects_invalid_triggered_by(db):
    """
    crawl_job.triggered_by must reference a real login row.
    SQLite must raise IntegrityError when the FK is violated.
    """
    user = make_login(db, "fk_test_user")
    src  = make_source(db, registered_by=user.login_id, url="https://fktest1.com")

    fake_login_id = uuid.uuid4()  # does NOT exist in the login table

    job = CrawlJob(
        triggered_by=fake_login_id,   # ← invalid FK
        source_id=src.source_id,
        status="pending",
    )
    db.add(job)

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 4 — FK violation: source_id references non-existent source
# ═════════════════════════════════════════════════════════════════════════════
def test_crawl_job_rejects_invalid_source_id(db):
    """
    crawl_job.source_id must reference a real source row.
    SQLite must raise IntegrityError when the FK is violated.
    """
    user = make_login(db, "fk_source_user")

    fake_source_id = uuid.uuid4()  # does NOT exist in the source table

    job = CrawlJob(
        triggered_by=user.login_id,
        source_id=fake_source_id,     # ← invalid FK
        status="pending",
    )
    db.add(job)

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 5 — FK violation: source.registered_by references non-existent login
# ═════════════════════════════════════════════════════════════════════════════
def test_source_rejects_invalid_registered_by(db):
    """
    source.registered_by must reference a real login row.
    """
    fake_login_id = uuid.uuid4()  # does NOT exist

    src = Source(
        name="Orphan Source",
        url="https://orphan.com",
        source_type="web",
        registered_by=fake_login_id,  # ← invalid FK
    )
    db.add(src)

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db.flush()


# ═════════════════════════════════════════════════════════════════════════════
# TEST 6 — FK ON DELETE RESTRICT: cannot delete a login that owns a crawl_job
# ═════════════════════════════════════════════════════════════════════════════
def test_cannot_delete_login_with_active_crawl_job(db):
    """
    Deleting a login that is referenced by a crawl_job must be rejected
    because the FK is defined with ON DELETE RESTRICT.
    """
    user = make_login(db, "restrict_user")
    src  = make_source(db, registered_by=user.login_id, url="https://restrict.com")

    job = CrawlJob(
        triggered_by=user.login_id,
        source_id=src.source_id,
        status="running",
    )
    db.add(job)
    db.flush()

    with pytest.raises(IntegrityError):
        db.delete(user)
        db.flush()   # FK RESTRICT must fire here
