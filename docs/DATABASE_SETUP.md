# DarkTrace M1 — Pod 2 Database & Integration Guide

Welcome to the shared database repository for **DarkTrace M1 — Pod 2**. This document is prepared by **Md Amir Ashraf (Database Setup & Integration Coordinator)** to provide clear, step-by-step instructions for all team members.

---

## 1. Project Database Purpose

The DarkTrace platform is an enterprise-grade dark-web monitoring and threat intelligence platform. The transactional database (PostgreSQL 16) serves as the **system of record** for:
- Registered monitoring sources and crawler execution jobs
- Keyword watchlists and immutable version history
- Deduplicated alerts with explainable threat scores
- Case investigations linking alerts, actors, and evidence
- Append-only, hash-chained audit event records

Our shared architecture follows the standard FastAPI + SQLAlchemy + PostgreSQL flow:
```text
FastAPI Router  ──>  Service Layer  ──>  SQLAlchemy Models  ──>  PostgreSQL Database
                                                                         ▲
                                                              Alembic Migrations
```

---

## 2. Team Responsibility & Module Ownership

Each team member owns a specific database table and corresponding backend module. **Do not modify another member's tables or files directly without coordination.**

| Team Member | Role | Assigned Tables / Modules | Key Files / Responsibilities |
| :--- | :--- | :--- | :--- |
| **Md Amir Ashraf** | **Database Setup & Integration Coordinator** | **Shared DB Infrastructure, Alerts & Integration** | Database engine, sessionmaker, base model, Alembic setup, alert deduplication, integration testing, docs |
| **Anil Kumar** | Source + Crawl Job | `source`, `crawl_job` | Source registry, crawl job tracking, crawling service & API |
| **Nikhil** | Watchlist + Watchlist Version | `watchlist`, `watchlist_version` | Regex/keyword rule watchlists, immutable version history |

---

## 3. Prerequisites

Before running the project locally, install:
- **Python 3.12+** (Python 3.12 or 3.14 tested)
- **PostgreSQL 16** (or Docker with PostgreSQL container)
- **Git**

---

## 4. Local PostgreSQL Setup

### Option A: Local PostgreSQL Service (Windows / Mac / Linux)
1. Install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/).
2. Start the PostgreSQL service.
3. Open `psql` or pgAdmin and create the dedicated database:
   ```sql
   CREATE DATABASE darktrace_pod2;
   ```
4. Verify your local username and password (default user is usually `postgres`).

### Option B: Docker Container (Recommended for clean isolation)
If Docker is installed:
```bash
docker run --name darktrace-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=darktrace_pod2 -p 5432:5432 -d postgres:16
```

---

## 5. Environment Variables & `.env` Setup

Never commit real credentials to Git!

1. Copy the example configuration template:
   ```bash
   cp .env.example .env
   # Or on Windows PowerShell:
   Copy-Item .env.example .env
   ```
2. Open `.env` and set your local database credentials:
   ```ini
   DATABASE_URL=postgresql+psycopg://postgres:your_local_password@localhost:5432/darktrace_pod2
   ENVIRONMENT=development
   DEBUG=True
   ```

> [!NOTE]
> We use the modern **Psycopg 3** driver (`postgresql+psycopg://...`).
> For quick offline unit testing without running PostgreSQL, you can temporarily set `DATABASE_URL=sqlite:///./dev.db`.

---

## 6. Installing Dependencies

Create and activate a virtual environment, then install dependencies:
```bash
# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell:
.venv\Scripts\Activate.ps1
# Or on Linux/macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

---

## 7. Verifying Database Connection

We have provided an automated verification script to test your database connectivity:
```bash
python scripts/test_db_connection.py
```
What this script verifies:
1. Validates that `DATABASE_URL` is parsed properly.
2. Performs a physical connection to PostgreSQL (`SELECT 1;`).
3. Verifies `SessionLocal` factory and transaction rollback.

---

## 8. Common Conventions Every Member Must Follow

To guarantee that all 6 modules integrate cleanly, all members must adhere to these conventions:

### A. Inherit from the Shared `Base`
**NEVER** call `Base = declarative_base()` inside your own file.
Always import the shared base:
```python
from app.db.base import Base, TimestampMixin
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer

class Source(Base, TimestampMixin):
    __tablename__ = "source"
    source_id: Mapped[str] = mapped_column(String, primary_key=True)
```
Inheriting from `app.db.base.Base` ensures that:
- Constraint names follow the project standard (`pk_...`, `fk_...`, `uq_...`, `ck_...`, `ix_...`).
- Alembic detects all tables across all members automatically.

### B. ID Conventions & Standard Prefixes
All primary keys use string identifiers with official prefixes (derived from the CyArt specification):
- `source_id`: `src_...` (e.g., `src_8842`)
- `job_id`: `job_...`
- `intent_id`: `ci_...`
- `watchlist_id`: `wl_...`
- `alert_id`: `alr_...`
- `case_id`: `case_...`
- `event_id`: `aud_...`
- `actor_id`: `act_...`
- `evidence_id`: `ev_...`
- `user_id`: `usr_...`

*(Exception: `audit_event` has a `BIGSERIAL` primary key `seq` for monotonic ordering, with a unique `event_id` text).*

### C. Timestamp Conventions
- Always use UTC timestamps with timezone: `DateTime(timezone=True)`.
- Use the shared `TimestampMixin` from `app.db.base` for tables that have `created_at` and `updated_at`.
- Use `TIMESTAMPTZ` in PostgreSQL DDL.

---

## 9. FastAPI Database Session Integration

When writing FastAPI route handlers, inject the database session using `Depends(get_db)`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

router = APIRouter(prefix="/sources", tags=["Sources"])

@router.get("/")
def list_sources(db: Session = Depends(get_db)):
    # db session is automatically opened and closed per request
    return db.query(Source).all()
```

---

## 10. Alembic Migrations Workflow

Alembic tracks database changes over time.

### Check Current Migration Status:
```bash
alembic current
```

### Create a New Migration (after adding or updating models):
```bash
alembic revision --autogenerate -m "create source and crawl_job tables"
```

### Apply Migrations to PostgreSQL:
```bash
alembic upgrade head
```

### Rollback the Last Migration:
```bash
alembic downgrade -1
```

> [!IMPORTANT]
> Md Amir Ashraf coordinates the final Alembic migration sequence and tests across the shared database foundation.

---

## 11. Running the Automated Tests

Run the test suite using `pytest`:
```bash
pytest -v
```

All 5 core database infrastructure tests should pass:
- Settings verification
- Constraint naming convention verification
- Session lifecycle & transaction test
- FastAPI `get_db` generator lifecycle test
- Alembic configuration validity test

---

## 12. Integration Checklist for Module Hand-off

Before submitting a pull request to merge your module into the backend:
- [ ] Model inherits from `app.db.base.Base`.
- [ ] Primary keys and foreign keys match the official prefixes and types.
- [ ] Timestamps use `DateTime(timezone=True)`.
- [ ] Unit tests pass with `pytest`.
- [ ] No real passwords, secrets, or `.env` files are committed.
- [ ] Migration script runs cleanly on a clean database (`alembic upgrade head`).
- [ ] FastAPI routes use `db: Session = Depends(get_db)`.
