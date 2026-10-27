"""
tests/test_api.py
API tests for FastAPI endpoints (Health, Sources, and Crawl Jobs).
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sqlalchemy.pool import StaticPool
from app.models.base import Base
from app.models.login import Login
from app.api.deps import get_db


@pytest.fixture
def client_and_db(monkeypatch):
    """Sets up an in-memory SQLite database and test client with overridden get_db."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)

    # Patch engine in app.database / app.db.session
    import app.database
    monkeypatch.setattr(app.database, "engine", test_engine)
    monkeypatch.setattr("app.main.create_tables", lambda: None)
    monkeypatch.setattr("app.main.verify_fk_enforcement", lambda: None)

    from app.main import app

    def override_get_db():
        with Session(test_engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed test user
    test_user_id = uuid.uuid4()
    with Session(test_engine) as session:
        user = Login(
            login_id=test_user_id,
            username="api_tester",
            email="api@darktrace.io",
            password_hash="argon2$fake",
            role="admin",
        )
        session.add(user)
        session.commit()

    with TestClient(app) as test_client:
        yield test_client, test_user_id

    app.dependency_overrides.clear()
    test_engine.dispose()


def test_api_health_endpoint(client_and_db):
    client, _ = client_and_db
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "source-crawl-job" in data["service"]


def test_api_create_and_list_sources(client_and_db):
    client, user_id = client_and_db
    source_payload = {
        "name": "DarkMarket Omega",
        "url": "http://omegator.onion",
        "source_type": "darkweb",
        "registered_by": str(user_id),
        "crawl_depth": 2,
        "crawl_frequency": "hourly",
    }
    create_resp = client.post("/sources/", json=source_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["name"] == "DarkMarket Omega"
    assert "source_id" in created_data

    # List sources
    list_resp = client.get("/sources/")
    assert list_resp.status_code == 200
    sources = list_resp.json()
    assert len(sources) >= 1
    assert any(s["name"] == "DarkMarket Omega" for s in sources)


def test_api_create_and_list_crawl_jobs(client_and_db):
    client, user_id = client_and_db
    # First create a source
    src_resp = client.post("/sources/", json={
        "name": "Pastebin Mirror",
        "url": "http://pastebinmirror.onion",
        "source_type": "darkweb",
        "registered_by": str(user_id),
    })
    assert src_resp.status_code == 201, f"Source creation failed: {src_resp.text}"
    src_id = src_resp.json()["source_id"]

    # Create crawl job
    job_payload = {
        "triggered_by": str(user_id),
        "source_id": src_id,
        "job_name": "Initial Discovery Job",
        "depth_used": 1,
    }
    job_resp = client.post("/crawl-jobs/", json=job_payload)
    assert job_resp.status_code == 201
    job_data = job_resp.json()
    assert job_data["status"] == "pending"
    assert job_data["source_id"] == src_id

    # List crawl jobs
    list_jobs = client.get("/crawl-jobs/")
    assert list_jobs.status_code == 200
    jobs = list_jobs.json()
    assert len(jobs) >= 1
    assert any(j["job_id"] == job_data["job_id"] for j in jobs)
