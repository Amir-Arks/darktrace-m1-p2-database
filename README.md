# DarkTrace M1 — Pod 2 Database & Backend Integration

Enterprise Dark Web Monitoring & Threat Intelligence Platform (Module 1 - Pod 2).

This repository provides the core database architecture, SQLAlchemy 2.0 ORM layer, Alembic migration framework, and FastAPI database session dependencies for Pod 2.

---

## 👥 Team & Responsibilities

| Member | Main Responsibility | Assigned Scope |
| :--- | :--- | :--- |
| **Md Amir Ashraf** | **Database Setup & Integration Coordinator** | **Shared DB foundation, session, Base, Alembic, conventions, coordination** |
| **Anil Kumar** | Source + Crawl Job | `source`, `crawl_job` tables, crawling service & API |
| **Nikhil** | Watchlist + Watchlist Version | `watchlist`, `watchlist_version` tables, versioning service & API |
| **Prakash K** | Alerts + Deduplication | `alert` table, fingerprinting, deduplication service & API |
| **Sriharish S** | Case + Investigation | `case_investigation` table, investigation service & API |
| **Varun Sahu** | Audit + Migrations + Final Testing | `audit_event` table, migration sequencing, clean DB integration tests |

---

## 🚀 Quickstart

### 1. Clone & Switch to your Branch
```bash
git clone https://github.com/Amir-Arks/darktrace-m1-p2-database.git
cd darktrace-m1-p2-database
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Local Environment
```bash
cp .env.example .env
# Edit .env with your local PostgreSQL credentials:
# DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/darktrace_pod2
```

### 4. Verify Database Connection
```bash
python scripts/test_db_connection.py
```

### 5. Run Test Suite
```bash
pytest -v
```

---

## 📚 Complete Guides & Documentation

- **[Detailed Database Setup & Integration Guide](docs/DATABASE_SETUP.md)**: Full guide covering PostgreSQL installation, Alembic migration workflow, common conventions, and module hand-off checklists.
- **[Railway Production Deployment Guide](docs/RAILWAY_DEPLOYMENT.md)**: Instructions for provisioning Railway PostgreSQL and deploying the FastAPI service.

---

## 🔒 Security Policy
- Never commit `.env`, passwords, or API keys.
- All secrets are managed via environment variables.
- Standard PostgreSQL connection pooling and health checks are configured in `app/db/session.py`.
