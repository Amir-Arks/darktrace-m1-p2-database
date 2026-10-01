# DarkTrace M1 — Pod 2 | M2: Database Layer
### Owner: Anil Kumar | Tables: `login`, `source`, `crawl_job`

---

## What M2 delivers

```
login (WHO is using the system)
  ↓
crawl_job (crawl job triggered by that user)
  ↓
source (which site the crawl_job is visiting)
```

M2 provides the database schema, SQLAlchemy models, migrations, and
connection setup. **M3 (backend) imports from this module** to build services and API routes on top.

---

## Project structure

```
cyart1/
│
├── schema_sqlite.sql       ← Raw DDL for SQLite  (dev / test)
├── schema_postgres.sql     ← Raw DDL for PostgreSQL  (prod)
├── alembic.ini             ← Alembic config
├── .env.example            ← Copy to .env and fill in DATABASE_URL
├── requirements.txt        ← M2-only Python deps
│
├── app/
│   ├── database.py         ← Engine, session factory, FK enforcement
│   └── models/
│       ├── base.py         ← SQLAlchemy DeclarativeBase
│       ├── login.py        ← Login model
│       ├── source.py       ← Source model
│       ├── crawl_job.py    ← CrawlJob model (FK → login + source)
│       └── __init__.py     ← Exports all models
│
├── migrations/
│   ├── env.py              ← Alembic env (reads DATABASE_URL)
│   └── versions/           ← Migration files go here
│
└── tests/
    ├── test_fk_enforcement.py  ← DB-level FK tests
    └── seed_data.py            ← Dummy data for Varun's integration tests
```

---

## Quick start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure database
```bash
cp .env.example .env
# Edit .env — leave SQLite for dev, or set PostgreSQL URL for prod
```

### 3. Create tables (SQLite dev)
```bash
python -c "from app.database import create_tables; create_tables()"
```

### 3b. Run migrations (PostgreSQL prod)
```bash
alembic upgrade head
```

### 4. Verify FK enforcement
```bash
python -c "from app.database import verify_fk_enforcement; verify_fk_enforcement()"
```

### 5. Insert seed data (for Varun's tests)
```bash
python tests/seed_data.py
```

### 6. Run DB tests
```bash
pytest tests/test_fk_enforcement.py -v
```

---

## Database selection

| Environment | `DATABASE_URL` in `.env` |
|---|---|
| Development | `sqlite:///./darktrace.db` ← default |
| Production  | `postgresql+psycopg2://user:pw@host:5432/dbname` |

The same SQLAlchemy models work on both. Only the URL changes.

---

## M3 (Backend) Handoff

M3 imports from this module:

```python
# In M3 dependencies.py — add this FastAPI dependency
from sqlalchemy.orm import Session
from app.database import SessionLocal
from typing import Generator

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

```python
# In M3 routes — import models directly
from app.models.login    import Login
from app.models.source   import Source
from app.models.crawl_job import CrawlJob
```

Call at M3 startup:
```python
from app.database import verify_fk_enforcement
verify_fk_enforcement()   # raises RuntimeError if SQLite FKs are off
```

---

## Table relationships

```
login  ──(1:many)──►  crawl_job  ◄──(many:1)──  source
  │                                                 ▲
  └──────────────────(1:many)──────────────────────┘
     (registered_by)
```

| FK | Direction | Constraint |
|---|---|---|
| `crawl_job.triggered_by` | → `login.login_id` | ON DELETE RESTRICT |
| `crawl_job.source_id` | → `source.source_id` | ON DELETE RESTRICT |
| `source.registered_by` | → `login.login_id` | ON DELETE RESTRICT |

---

## SQLite FK enforcement (solved)

SQLite does not enforce FKs by default. Three layers ensure it is always ON:

| Layer | Where | What it does |
|---|---|---|
| 1 | `connect` event | Applies `PRAGMA foreign_keys = ON` on new connections |
| 2 | `checkout` event | Re-applies PRAGMA every time a connection leaves the pool |
| 3 | `verify_fk_enforcement()` | Reads PRAGMA at startup — raises `RuntimeError` if OFF |

---

## Git branch

```
db/source-crawl    ← Anil's branch (this module)
```
