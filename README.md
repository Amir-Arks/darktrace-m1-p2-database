# Watchlist Database (PostgreSQL)

**Owner:** Nikhil Kalokhe  
**Scope:** `watchlist` and `watchlist_version` tables, version history, constraints, sample data, and SQL tests.

## What this implements

- A stable watchlist record with an owner and identity.
- Separate version records so edits do not overwrite older configurations.
- Expression, scope, severity, creator, and timestamp stored per version.
- A unique version number per watchlist.
- A current-version pointer that must point to a version belonging to the same watchlist.
- Example data with two versions of one watchlist.
- A test script that checks creation, version retrieval, current-version selection, and preservation of history.

## Requirements

- PostgreSQL 13+ (uses standard PostgreSQL features).
- A database/schema where you have permission to create tables.

## Run it

From this directory, run the files in this order with `psql`:

```bash
psql -d YOUR_DATABASE -f migrations/001_create_watchlist_tables.sql
psql -d YOUR_DATABASE -f examples/002_seed_example_data.sql
psql -d YOUR_DATABASE -f tests/003_test_watchlist_versioning.sql
```

If you prefer a single command:

```bash
psql -d YOUR_DATABASE -f migrations/001_create_watchlist_tables.sql
psql -d YOUR_DATABASE -f examples/002_seed_example_data.sql
psql -d YOUR_DATABASE -f tests/003_test_watchlist_versioning.sql
```

Replace `YOUR_DATABASE` with your PostgreSQL database name. The seed script uses fixed example IDs and is intended for a fresh database created with the migration.

## Useful queries

Get the current version of each watchlist:

```sql
SELECT w.watchlist_id, w.name, v.version_number, v.expression, v.scope, v.severity
FROM watchlist AS w
JOIN watchlist_version AS v
  ON v.watchlist_id = w.watchlist_id
 AND v.version_id = w.current_version_id;
```

Get all versions for one watchlist, newest first:

```sql
SELECT version_number, expression, scope, severity, created_by, created_at
FROM watchlist_version
WHERE watchlist_id = 1001
ORDER BY version_number DESC;
```

## Versioning rule

When the configuration changes, insert a new row into `watchlist_version` with the next version number, then update `watchlist.current_version_id`. Do **not** update the previous version's expression/scope/severity to represent the new configuration. Historical versions remain available.

## Notes / integration

This is a PostgreSQL reference implementation because the project database engine was not specified in the task description. If the repository already uses another database (for example, MySQL or SQLite), adapt the migration syntax and test approach to that database before merging. The schema uses text fields for `expression`, `scope`, and `severity`; tighten them to enums/check constraints if your project defines an agreed vocabulary.
