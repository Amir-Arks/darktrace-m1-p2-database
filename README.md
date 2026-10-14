# Database helpers

One place to connect to every database in the project. Each helper reads its
settings from environment variables (copy `.env.example` to `.env`), retries
with backoff, and raises a clear `DatabaseConnectionError` if the server is down.

| Database | Helper | Returns |
|---|---|---|
| PostgreSQL (SQLite if `DATABASE_URL` unset) | `get_engine()`, `get_session()`, `session_scope()` | SQLAlchemy Engine / Session |
| MongoDB | `get_mongo_client()`, `get_mongo_db()` | pymongo client / database |
| Redis | `get_redis()` | redis client |
| Elasticsearch | `get_elasticsearch()` | Elasticsearch client |
| Neo4j | `get_neo4j_driver()` | Neo4j driver |
| All | `check_all()` | `{name: {"ok": bool, "error": str|None}}` |

Clients are created once and reused (cached).

## Usage

```python
from db import session_scope, get_mongo_db, get_redis, check_all

with session_scope() as s:          # commits on success, rolls back on error
    s.execute(text("SELECT 1"))

posts = get_mongo_db()["posts"]
get_redis().set("key", "value", ex=60)
print(check_all())                  # or: python -m db.health
```

## Run tests

```bash
pip install -r requirements.txt
pytest -q
```
Tests use in-memory SQLite and confirm the other four fail with a clear error
when no server is running. They do not need real servers.

## Notes
- Passwords live only in `.env` (ignored by git). Never commit it.
- Edit `db/config.py` and `.env.example` if your project uses different databases.
