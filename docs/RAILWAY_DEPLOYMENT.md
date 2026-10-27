# Railway Deployment Guide — DarkTrace M1 Pod 2

This guide outlines the production deployment procedure for the **DarkTrace M1 Pod 2 Backend and Database** on Railway.

---

## 1. Architecture Overview on Railway

- **Web Service**: FastAPI application (`app.main:app`), executed via Uvicorn.
- **Relational Database**: Railway-managed **PostgreSQL 16** service.
- **ORM / Migrations**: SQLAlchemy 2.0 with Psycopg 3 (`psycopg[binary]`), managed via Alembic.

---

## 2. Environment Variables Configuration

Railway automatically provides the `DATABASE_URL` environment variable when a PostgreSQL plugin is provisioned.

The application (`app.core.config.Settings`) automatically normalizes standard connection strings:
- `postgres://user:pass@host:port/db`
  ➔ Automatically translated at runtime to `postgresql+psycopg://user:pass@host:port/db`

### Recommended Railway Service Variables:
| Variable | Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Injected automatically by Railway PostgreSQL |
| `ENVIRONMENT` | `production` | Sets execution mode to production |
| `DEBUG` | `False` | Disables verbose debug logging |
| `API_V1_PREFIX` | `/api/v1` | Base API prefix |
| `DB_POOL_SIZE` | `5` | Active connection pool limit |
| `DB_MAX_OVERFLOW`| `10` | Overflow connections allowed |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait before timing out pool checkout |

---

## 3. Step-by-Step Deployment Procedure

### Step 1: Create a Railway Project
1. Log in to your [Railway Dashboard](https://railway.app).
2. Click **New Project** ➔ **Deploy from GitHub repo**.
3. Select `darktrace-m1-p2-database`.

### Step 2: Add PostgreSQL Database Service
1. In the project canvas, click **+ New** ➔ **Database** ➔ **Add PostgreSQL**.
2. Railway provisions a dedicated PostgreSQL instance.

### Step 3: Link Database to the Web Service
1. Open your Web Service settings ➔ **Variables**.
2. Add reference variable:
   - Name: `DATABASE_URL`
   - Value: `${{Postgres.DATABASE_URL}}`

### Step 4: Run Database Migrations
Run the Alembic migration command in the Railway service terminal (or via Railway CLI):
```bash
alembic upgrade head
```
This executes all 3 migration revisions in order:
1. `c3acc2cc0045`: Creates `login`, `source`, and `crawl_job` tables.
2. `w001_watchlist`: Creates `watchlist` and `watchlist_version` tables.
3. `a001_alert`: Creates `alert` table with foreign keys to `source` and `watchlist`.

### Step 5: Verify Deployment Health
Send a GET request to the deployed application:
```bash
curl https://<your-railway-app-domain>.up.railway.app/health
```
Expected response:
```json
{
  "status": "healthy",
  "service": "source-crawl-job",
  "db": "[DarkTrace DB] PostgreSQL | postgresql+psycopg://postgres:***@...:5432/railway"
}
```

---

## 4. Post-Deployment Smoke Testing

To verify data persistence and relationship integrity:
1. Visit the interactive Swagger documentation at `https://<your-app>.up.railway.app/docs`.
2. Verify:
   - `POST /sources/`: Successfully registers a test source.
   - `GET /sources/`: Returns the registered source.
   - `POST /crawl-jobs/`: Successfully creates a crawl job linked to the source.
   - Nonexistent foreign keys are rejected with `HTTP 400`.
