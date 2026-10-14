# Alert Table (Dark Web Monitor)

Owner: Nikhil Kalokhe, role: Alert Database Table

## What is here

| File | Purpose |
|---|---|
| `app/models/alert.py` | `Alert` model, enums, fingerprint, dedup (`record_alert`), state machine (`transition_alert`) |
| `app/models/references.py` | **Temporary** `Source` / `Watchlist` stand-ins (delete when real models are merged) |
| `alembic/versions/0001_create_alert_table.py` | Migration: table, constraints, indexes |
| `alembic/versions/0000_stub_source_watchlist.py` | **Temporary** stub migration (delete when merged) |
| `tests/test_alert.py` | 22 tests: normal alerts, duplicates, state transitions, constraints, indexes |

## Fields

`alert_id, fingerprint, source_id, doc_id, watchlist_id, severity, confidence, threat_score, explain_ref, state, assigned_to, escalated_at, first_seen, last_seen, count`

- `source_id` -> FK `source.source_id` (RESTRICT)
- `watchlist_id` -> FK `watchlist.watchlist_id` (SET NULL, optional)
- `doc_id` is a plain column for now (document table belongs to another pod; add FK later)
- `severity`: low / medium / high / critical
- `confidence`: 0.0 to 1.0, `threat_score`: 0 to 100 (both enforced by CHECK constraints)
- `state`: new, acknowledged, investigating, escalated, resolved, false_positive

## Deduplication

`fingerprint = sha256(source_id | watchlist_id | normalised key)` and is UNIQUE.
`record_alert()` inserts a new alert, or if the fingerprint exists it does
`count += 1`, updates `last_seen`, and keeps the highest severity / confidence / threat score.
Rules: a **resolved** alert re-opens to `new` on a repeat; a **false_positive** stays suppressed (count still goes up).
If two workers insert the same fingerprint at once, the unique constraint catches it and the loser is treated as a duplicate.

## State transitions

```
new -> acknowledged | investigating | escalated | false_positive
acknowledged -> investigating | escalated | resolved | false_positive
investigating -> escalated | resolved | false_positive
escalated -> investigating | resolved
resolved -> new            (re-open)
false_positive -> new      (re-open)
```
Moving to `escalated` sets `escalated_at`. Invalid moves raise `InvalidStateTransition`.

## Indexes

`fingerprint` (unique), `state`, `severity`, `source_id`, `watchlist_id`, `(state, severity)` for the analyst queue, `last_seen`.

## Run

```bash
pip install -r requirements.txt
pytest -q                 # 22 tests
alembic upgrade head      # set sqlalchemy.url in alembic.ini first
alembic downgrade 0000_stub
```

## When merging with the team

1. Delete `app/models/references.py` and `alembic/versions/0000_stub_source_watchlist.py`.
2. Import the real `Source` / `Watchlist` in `app/models/__init__.py`.
3. Set `down_revision` in `0001_create_alert_table.py` to the real latest revision.
